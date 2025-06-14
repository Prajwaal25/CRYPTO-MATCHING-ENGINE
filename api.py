
from fastapi import FastAPI, WebSocket
from pydantic import BaseModel
from order_book import OrderBook
from order import Order
from datetime import datetime

app = FastAPI()
order_book = OrderBook("BTC-USDT")

class OrderRequest(BaseModel):
    symbol: str
    order_type: str
    side: str
    quantity: float
    price: float = None

@app.post("/submit_order")
def submit_order(order: OrderRequest):
    new_order = Order(**order.dict())
    trades = order_book.add_order(new_order)
    return {"order_id": new_order.order_id, "trades": len(trades)}

@app.websocket("/ws/market_data")
async def market_data(websocket: WebSocket):
    await websocket.accept()
    while True:
        bbo = order_book.get_bbo()
        depth = order_book.get_depth()
        data = {
            "timestamp": datetime.utcnow().isoformat(),
            "symbol": "BTC-USDT",
            "asks": depth["asks"],
            "bids": depth["bids"],
            "bbo": bbo
        }
        await websocket.send_json(data)
