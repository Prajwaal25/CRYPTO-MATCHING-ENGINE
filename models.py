from pydantic import BaseModel, Field
from typing import Optional, List
from uuid import UUID, uuid4
from datetime import datetime

class Order(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    symbol: str
    order_type: str  # "market", "limit", "ioc", "fok"
    side: str        # "buy" or "sell"
    quantity: float
    price: Optional[float] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)

class OrderRequest(BaseModel):
    symbol: str
    order_type: str  # "market", "limit", "ioc", "fok"
    side: str        # "buy", "sell"
    quantity: float
    price: Optional[float] = None

class OrderResponse(BaseModel):
    order_id: UUID
    trades: int
    status: str = "accepted"

class Trade(BaseModel):
    trade_id: UUID = Field(default_factory=uuid4)
    symbol: str
    price: float
    quantity: float
    aggressor_side: str  # "buy" or "sell"
    maker_order_id: UUID
    taker_order_id: UUID
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")

class TradeExecution(BaseModel):
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")
    symbol: str
    trade_id: str
    price: float
    quantity: float
    aggressor_side: str
    maker_order_id: str
    taker_order_id: str

# Added L2Snapshot alias for backward compatibility
class L2Snapshot(BaseModel):
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")
    symbol: str
    bids: List[List[float]]  # [[price, quantity], ...]
    asks: List[List[float]]  # [[price, quantity], ...]

class L2OrderBookSnapshot(BaseModel):
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")
    symbol: str
    bids: List[List[float]]  # [[price, quantity], ...]
    asks: List[List[float]]  # [[price, quantity], ...]

class BBO(BaseModel):
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")
    symbol: str
    bid: Optional[float] = None
    ask: Optional[float] = None
    
class Order(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    symbol: str
    order_type: str  # "market", "limit", "ioc", "fok"
    side: str        # "buy" or "sell"
    quantity: float
    price: Optional[float] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    # 🚨 New fields for stop/conditional orders
    trigger_price: Optional[float] = None
    trigger_type: Optional[str] = None
