import uuid
from datetime import datetime
from typing import Optional

class Order:
    def __init__(self, symbol: str, side: str, order_type: str, quantity: float, price: Optional[float] = None):
        self.id = str(uuid.uuid4())
        self.symbol = symbol
        self.side = side  # 'buy' or 'sell'
        self.order_type = order_type  # 'market', 'limit', 'ioc', 'fok'
        self.quantity = quantity
        self.original_quantity = quantity
        self.price = price
        self.timestamp = datetime.utcnow()
        self.status = "new"  # new, partial, filled, cancelled
    
    def __str__(self):
        return f"Order({self.id[:8]}, {self.side} {self.quantity}@{self.price}, {self.order_type})"
    
    def __repr__(self):
        return self.__str__()
    
    def is_market_order(self) -> bool:
        return self.order_type == "market"
    
    def is_limit_order(self) -> bool:
        return self.order_type == "limit"
    
    def is_ioc_order(self) -> bool:
        return self.order_type == "ioc"
    
    def is_fok_order(self) -> bool:
        return self.order_type == "fok"
    
    def is_buy(self) -> bool:
        return self.side == "buy"
    
    def is_sell(self) -> bool:
        return self.side == "sell"
    
    def reduce_quantity(self, amount: float):
        """Reduce the order quantity by the specified amount"""
        self.quantity = max(0, self.quantity - amount)
        if self.quantity == 0:
            self.status = "filled"
        elif self.quantity < self.original_quantity:
            self.status = "partial"















