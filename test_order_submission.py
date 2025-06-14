import requests
import time

BASE_URL = "http://localhost:8000"

def submit_order(symbol, order_type, side, quantity, price=None):
    payload = {
        "symbol": symbol,
        "order_type": order_type,
        "side": side,
        "quantity": quantity
    }
    if order_type == "limit":
        payload["price"] = price

    response = requests.post(f"{BASE_URL}/submit_order", json=payload)
    print(f"\nSubmitted {side.upper()} {order_type.upper()} order:")
    print(response.json())

# Step 1: Submit Buy Order
submit_order(symbol="BTC-USDT", order_type="limit", side="buy", quantity=1, price=30000)

# Optional wait to simulate order resting in book
time.sleep(1)

# Step 2: Submit Sell Order
submit_order(symbol="BTC-USDT", order_type="limit", side="sell", quantity=1, price=30000)
