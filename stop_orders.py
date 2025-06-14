# stop_orders.py

import asyncio
from collections import defaultdict
from typing import List, Dict
from models import Order
import uuid
import logging

logger = logging.getLogger("StopOrders")

# Storage for pending stop orders
stop_orders_by_symbol: Dict[str, List[Order]] = defaultdict(list)
engine = None  # placeholder
def set_engine(e):
    global engine
    engine = e


def add_stop_order(order: Order):
    stop_orders_by_symbol[order.symbol].append(order)
    logger.info(f"Stop order added: {order.id} for {order.symbol} @ trigger {order.trigger_price}")


def should_trigger(order: Order, bbo: Dict) -> bool:
    if not order.trigger_price or not order.trigger_type:
        return False

    bid = bbo.get("bid")
    ask = bbo.get("ask")

    if order.trigger_type == "stop_loss":
        if order.side == "sell" and bid is not None and bid <= order.trigger_price:
            return True
        if order.side == "buy" and ask is not None and ask >= order.trigger_price:
            return True

    elif order.trigger_type == "take_profit":
        if order.side == "sell" and bid is not None and bid >= order.trigger_price:
            return True
        if order.side == "buy" and ask is not None and ask <= order.trigger_price:
            return True

    elif order.trigger_type == "stop_limit":
        if order.side == "buy" and ask is not None and ask >= order.trigger_price:
            return True
        if order.side == "sell" and bid is not None and bid <= order.trigger_price:
            return True

    return False


async def monitor_stop_orders():
    while True:
        for symbol, orders in list(stop_orders_by_symbol.items()):
            bbo = engine.get_bbo(symbol)
            to_trigger = []

            for order in orders:
                if should_trigger(order, bbo):
                    to_trigger.append(order)

            for order in to_trigger:
                stop_orders_by_symbol[symbol].remove(order)
                # Transform stop -> real order
                logger.info(f"Triggering stop order {order.id} for {symbol}")
                order.trigger_price = None
                order.trigger_type = None
                order.id = uuid.uuid4()
                engine.process_order(order)
        await asyncio.sleep(0.5)
