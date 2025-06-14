import logging
from typing import Dict, List, Tuple, Optional
from collections import defaultdict
from datetime import datetime

from models import Order, Trade
from trade_log import log_trade

logger = logging.getLogger("MatchingEngine")

def normalize_price(price: float) -> float:
    return round(price, 2)


class PriceLevel:
    def __init__(self, price: float):
        self.price = normalize_price(price)
        self.orders: List[Order] = []
        self.total_quantity = 0.0

    def add_order(self, order: Order):
        self.orders.append(order)
        self.total_quantity += order.quantity

    def remove_order(self, order: Order):
        if order in self.orders:
            self.total_quantity -= order.quantity
            self.orders.remove(order)

    def is_empty(self):
        return len(self.orders) == 0


class OrderBook:
    def __init__(self, symbol: str):
        self.symbol = symbol
        self.bids: Dict[float, PriceLevel] = {}  # Buy orders, sorted high to low
        self.asks: Dict[float, PriceLevel] = {}  # Sell orders, sorted low to high
        self.orders: Dict[str, Order] = {}

    def add_order(self, order: Order):
        self.orders[str(order.id)] = order
        price_key = normalize_price(order.price)
        book = self.bids if order.side == "buy" else self.asks

        if price_key not in book:
            book[price_key] = PriceLevel(price_key)
        book[price_key].add_order(order)

    def remove_order(self, order: Order):
        price_key = normalize_price(order.price)
        book = self.bids if order.side == "buy" else self.asks

        if price_key in book:
            book[price_key].remove_order(order)
            if book[price_key].is_empty():
                del book[price_key]
        self.orders.pop(str(order.id), None)

    def get_best_bid(self) -> Optional[float]:
        return max(self.bids.keys()) if self.bids else None

    def get_best_ask(self) -> Optional[float]:
        return min(self.asks.keys()) if self.asks else None

    def get_depth(self, levels: int = 10) -> Dict:
        bids = sorted(self.bids.items(), key=lambda x: -x[0])[:levels]
        asks = sorted(self.asks.items(), key=lambda x: x[0])[:levels]
        return {
            "bids": [[price, level.total_quantity] for price, level in bids],
            "asks": [[price, level.total_quantity] for price, level in asks],
        }

class MatchingEngine:
    def __init__(self):
        self.order_books: Dict[str, OrderBook] = {}

    def _get_order_book(self, symbol: str) -> OrderBook:
        if symbol not in self.order_books:
            self.order_books[symbol] = OrderBook(symbol)
        return self.order_books[symbol]

    def process_order(self, order: Order) -> List[Trade]:
        book = self._get_order_book(order.symbol)
        trades = []

        if order.order_type == "market":
            trades = self._execute_market_order(book, order)
        elif order.order_type == "limit":
            trades = self._execute_limit_order(book, order)
        elif order.order_type == "ioc":
            trades = self._execute_limit_order(book, order, ioc=True)
        elif order.order_type == "fok":
            if self._can_fully_fill(book, order):
                trades = self._execute_limit_order(book, order)

        return trades

    def _can_fully_fill(self, book: OrderBook, order: Order) -> bool:
        total = 0.0
        price_key = normalize_price(order.price)

        if order.side == "buy":
            for price in sorted(book.asks):
                if price > price_key:
                    break
                total += book.asks[price].total_quantity
                if total >= order.quantity:
                    return True
        else:
            for price in sorted(book.bids, reverse=True):
                if price < price_key:
                    break
                total += book.bids[price].total_quantity
                if total >= order.quantity:
                    return True
        return False

    def _execute_market_order(self, book: OrderBook, order: Order) -> List[Trade]:
        return self._match_order(book, order, market=True)

    def _execute_limit_order(self, book: OrderBook, order: Order, ioc=False) -> List[Trade]:
        trades = self._match_order(book, order)
        if order.quantity > 0 and not ioc:
            book.add_order(order)
        return trades

    def _match_order(self, book: OrderBook, order: Order, market=False) -> List[Trade]:
        trades = []
        is_buy = order.side == "buy"
        opposite_book = book.asks if is_buy else book.bids
        price_levels = sorted(opposite_book.keys()) if is_buy else sorted(opposite_book.keys(), reverse=True)

        for price in price_levels:
            if not market and (
                (is_buy and price > normalize_price(order.price)) or
                (not is_buy and price < normalize_price(order.price))
            ):
                break

            level = opposite_book[price]
            for resting_order in level.orders[:]:
                if order.quantity <= 0:
                    break

                traded_qty = min(order.quantity, resting_order.quantity)
                order.quantity -= traded_qty
                resting_order.quantity -= traded_qty

                trade = log_trade(
                    symbol=order.symbol,
                    price=price,
                    quantity=traded_qty,
                    aggressor_side=order.side,
                    maker_order_id=str(resting_order.id),
                    taker_order_id=str(order.id)
                )
                trades.append(trade)

                if resting_order.quantity <= 0:
                    book.remove_order(resting_order)

            if level.is_empty():
                del opposite_book[price]

            if order.quantity <= 0:
                break

        return trades

    def get_order_book_depth(self, symbol: str, levels: int = 10) -> Dict:
        book = self.order_books.get(symbol)
        if not book:
            return {"symbol": symbol, "bids": [], "asks": [], "timestamp": datetime.utcnow().isoformat() + "Z"}
        depth = book.get_depth(levels)
        return {
            "symbol": symbol,
            "bids": depth["bids"],
            "asks": depth["asks"],
            "timestamp": datetime.utcnow().isoformat() + "Z"
        }

    def get_bbo(self, symbol: str) -> Dict:
        book = self.order_books.get(symbol)
        if not book:
            return {"symbol": symbol, "bid": None, "ask": None, "timestamp": datetime.utcnow().isoformat() + "Z"}
        return {
            "symbol": symbol,
            "bid": book.get_best_bid(),
            "ask": book.get_best_ask(),
            "timestamp": datetime.utcnow().isoformat() + "Z"
        }

    def cancel_order(self, symbol: str, order_id: str) -> bool:
        book = self.order_books.get(symbol)
        if not book or order_id not in book.orders:
            return False
        order = book.orders[order_id]
        return book.remove_order(order)

    def get_order_status(self, symbol: str, order_id: str) -> Optional[Order]:
        book = self.order_books.get(symbol)
        if not book:
            return None
        return book.orders.get(order_id)
