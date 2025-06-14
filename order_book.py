from collections import defaultdict, deque
import heapq
import logging
from typing import List, Tuple, Optional, Dict
from order import Order
from trade_log import log_trade

logger = logging.getLogger("OrderBook")

class OrderBook:
    def __init__(self, symbol: str):
        self.symbol = symbol
        
        # Price levels: price -> deque of orders (FIFO within price level)
        self.bids: Dict[float, deque] = defaultdict(deque)  # buy orders
        self.asks: Dict[float, deque] = defaultdict(deque)  # sell orders
        
        # Heaps for efficient best price lookup
        self.bid_prices = []  # max-heap (negated prices for max behavior)
        self.ask_prices = []  # min-heap
        
        # Track all active orders by ID
        self.active_orders: Dict[str, Order] = {}
        
        logger.info(f"OrderBook initialized for {symbol}")

    def add_order(self, order: Order) -> List[Tuple]:
        """Add an order to the book and return list of trades"""
        logger.info(f"Processing order: {order}")
        
        # Handle market orders by setting extreme prices
        if order.is_market_order():
            if order.is_buy():
                order.price = float('inf')  # Will match any ask price
            else:
                order.price = 0.0  # Will match any bid price
        
        # Store original quantity for FOK validation
        original_quantity = order.quantity
        
        # Attempt to match the order
        trades = self._match_order(order)
        
        # Handle FOK orders - if not fully filled, reject entire order
        if order.is_fok_order():
            filled_quantity = sum(trade[3] for trade in trades)  # trade[3] is quantity
            if filled_quantity < original_quantity:
                logger.info(f"FOK order {order.id[:8]} rejected - not fully filled")
                # Restore order book state (this is simplified - in production you'd need proper rollback)
                return []
        
        # Handle IOC orders - any remaining quantity is cancelled
        if order.is_ioc_order():
            if order.quantity > 0:
                logger.info(f"IOC order {order.id[:8]} - cancelling remaining quantity: {order.quantity}")
                order.quantity = 0
        
        # Add remaining quantity to book for limit orders only
        if order.quantity > 0 and order.is_limit_order():
            self._add_to_book(order)
        
        return trades

    def _match_order(self, incoming_order: Order) -> List[Tuple]:
        """Match an incoming order against the opposite side of the book"""
        trades = []
        
        # Get the opposite book and price levels
        if incoming_order.is_buy():
            opposite_book = self.asks
            opposite_prices = self.ask_prices
        else:
            opposite_book = self.bids
            opposite_prices = self.bid_prices
        
        # Match against best prices first
        while incoming_order.quantity > 0 and opposite_prices:
            # Get best price from opposite side
            if incoming_order.is_buy():
                best_price = opposite_prices[0]  # min price for asks
            else:
                best_price = -opposite_prices[0]  # max price for bids (negated)
            
            # Check if we can match at this price level
            if not self._can_match(incoming_order, best_price):
                break
            
            # Match orders at this price level
            orders_at_price = opposite_book[best_price]
            
            while orders_at_price and incoming_order.quantity > 0:
                resting_order = orders_at_price[0]  # First order (FIFO)
                
                # Calculate trade quantity
                trade_quantity = min(incoming_order.quantity, resting_order.quantity)
                trade_price = resting_order.price  # Price-time priority: use resting order price
                
                # Execute the trade
                trades.append((incoming_order, resting_order, trade_price, trade_quantity))
                
                # Log the trade
                log_trade(incoming_order, resting_order, trade_price, trade_quantity)
                
                # Update order quantities
                incoming_order.reduce_quantity(trade_quantity)
                resting_order.reduce_quantity(trade_quantity)
                
                # Remove filled orders
                if resting_order.quantity == 0:
                    orders_at_price.popleft()
                    del self.active_orders[resting_order.id]
                    logger.info(f"Order {resting_order.id[:8]} fully filled and removed")
            
            # Clean up empty price levels
            if not orders_at_price:
                if incoming_order.is_buy():
                    heapq.heappop(opposite_prices)  # Remove from ask_prices
                else:
                    heapq.heappop(opposite_prices)  # Remove from bid_prices
                del opposite_book[best_price]
        
        return trades

    def _can_match(self, order: Order, price: float) -> bool:
        """Check if an order can match at the given price"""
        if order.is_market_order():
            return True
        
        if order.is_buy():
            return order.price >= price  # Buy order can match at or below its limit
        else:
            return order.price <= price  # Sell order can match at or above its limit

    def _add_to_book(self, order: Order):
        """Add a limit order to the appropriate side of the book"""
        self.active_orders[order.id] = order
        
        if order.is_buy():
            # Add to bids
            if order.price not in self.bids:
                heapq.heappush(self.bid_prices, -order.price)  # Negative for max-heap behavior
            self.bids[order.price].append(order)
            logger.info(f"Added buy order {order.id[:8]} to book at ${order.price}")
        else:
            # Add to asks
            if order.price not in self.asks:
                heapq.heappush(self.ask_prices, order.price)
            self.asks[order.price].append(order)
            logger.info(f"Added sell order {order.id[:8]} to book at ${order.price}")

    def cancel_order(self, order_id: str) -> bool:
        """Cancel an order by ID"""
        if order_id not in self.active_orders:
            return False
        
        order = self.active_orders[order_id]
        
        # Remove from appropriate book
        if order.is_buy():
            self.bids[order.price].remove(order)
            if not self.bids[order.price]:
                del self.bids[order.price]
                # Note: Not removing from bid_prices heap for simplicity
                # In production, you'd need a more sophisticated approach
        else:
            self.asks[order.price].remove(order)
            if not self.asks[order.price]:
                del self.asks[order.price]
        
        del self.active_orders[order_id]
        order.status = "cancelled"
        logger.info(f"Cancelled order {order_id[:8]}")
        return True

    def get_bbo(self) -> dict:
        """Get Best Bid and Offer"""
        best_bid = -self.bid_prices[0] if self.bid_prices else None
        best_ask = self.ask_prices[0] if self.ask_prices else None
        
        # Clean up empty price levels in heaps
        while self.bid_prices and (-self.bid_prices[0] not in self.bids or not self.bids[-self.bid_prices[0]]):
            heapq.heappop(self.bid_prices)
            best_bid = -self.bid_prices[0] if self.bid_prices else None
        
        while self.ask_prices and (self.ask_prices[0] not in self.asks or not self.asks[self.ask_prices[0]]):
            heapq.heappop(self.ask_prices)
            best_ask = self.ask_prices[0] if self.ask_prices else None
        
        return {"bid": best_bid, "ask": best_ask}

    def get_depth(self, levels: int = 10) -> dict:
        """Get order book depth (top N levels)"""
        # Build bid depth (highest to lowest)
        bid_depth = []
        seen_bid_prices = set()
        temp_bid_prices = [p for p in self.bid_prices]  # Copy heap
        
        while temp_bid_prices and len(bid_depth) < levels:
            price = -heapq.heappop(temp_bid_prices)
            if price in self.bids and self.bids[price] and price not in seen_bid_prices:
                total_quantity = sum(order.quantity for order in self.bids[price])
                if total_quantity > 0:
                    bid_depth.append([price, total_quantity])
                    seen_bid_prices.add(price)
        
        # Build ask depth (lowest to highest)
        ask_depth = []
        seen_ask_prices = set()
        temp_ask_prices = [p for p in self.ask_prices]  # Copy heap
        
        while temp_ask_prices and len(ask_depth) < levels:
            price = heapq.heappop(temp_ask_prices)
            if price in self.asks and self.asks[price] and price not in seen_ask_prices:
                total_quantity = sum(order.quantity for order in self.asks[price])
                if total_quantity > 0:
                    ask_depth.append([price, total_quantity])
                    seen_ask_prices.add(price)
        
        return {"bids": bid_depth, "asks": ask_depth}

    def get_order_count(self) -> dict:
        """Get count of active orders"""
        return {
            "total_orders": len(self.active_orders),
            "bid_orders": sum(len(orders) for orders in self.bids.values()),
            "ask_orders": sum(len(orders) for orders in self.asks.values())
        }