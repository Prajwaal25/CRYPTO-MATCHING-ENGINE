import os
import json
from typing import Dict
from models import Order
from uuid import UUID

SAVE_DIR = "orderbook_data"
os.makedirs(SAVE_DIR, exist_ok=True)

def save_order_book_state(order_books: Dict[str, any]):
    for symbol, book in order_books.items():
        orders = [o.dict() for o in book.orders.values() if o.quantity > 0]
        with open(f"{SAVE_DIR}/{symbol}.json", "w") as f:
            json.dump(orders, f, indent=2)

def load_order_book_state(order_books: Dict[str, any], engine):
    for filename in os.listdir(SAVE_DIR):
        if filename.endswith(".json"):
            symbol = filename.replace(".json", "")
            try:
                with open(f"{SAVE_DIR}/{filename}", "r") as f:
                    orders = json.load(f)
                    for o in orders:
                        o['id'] = UUID(o['id'])
                        order = Order(**o)
                        engine.process_order(order)
            except Exception as e:
                print(f"[load_state] Skipping corrupted file {filename}: {e}")
