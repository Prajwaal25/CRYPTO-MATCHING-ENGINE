import logging
import json
import os
import uuid
from datetime import datetime
from typing import List, Dict
from collections import defaultdict, deque
from models import Trade

logger = logging.getLogger(__name__)

trade_history: List[Trade] = []
symbol_trades: Dict[str, deque] = defaultdict(lambda: deque(maxlen=1000))

TRADES_FILE = "trades.jsonl"

MAKER_FEE_RATE = 0.0005  # 0.05%
TAKER_FEE_RATE = 0.001   # 0.10%

def log_trade(symbol: str, price: float, quantity: float, aggressor_side: str,
              maker_order_id: str, taker_order_id: str) -> Trade:
    try:
        taker_fee = price * quantity * TAKER_FEE_RATE
        maker_fee = price * quantity * MAKER_FEE_RATE

        trade = Trade(
            symbol=symbol,
            price=price,
            quantity=quantity,
            aggressor_side=aggressor_side,
            maker_order_id=uuid.UUID(str(maker_order_id)),
            taker_order_id=uuid.UUID(str(taker_order_id)),
            maker_fee=round(maker_fee, 4),
            taker_fee=round(taker_fee, 4)
        )

        trade_history.append(trade)
        symbol_trades[symbol].append(trade)

        with open(TRADES_FILE, "a") as f:
            f.write(trade.json() + "\n")

        logger.info(f"Trade logged: {symbol} {quantity}@{price} ({aggressor_side})")
        return trade

    except Exception as e:
        logger.error(f"Error logging trade: {str(e)}")
        raise

def get_recent_trades(symbol: str, limit: int = 20) -> List[Trade]:
    """Get recent trades for a symbol"""
    if symbol not in symbol_trades:
        return []
    return list(symbol_trades[symbol])[-limit:][::-1]

def get_all_trade_history(limit: int = 100) -> List[Trade]:
    return trade_history[-limit:][::-1]
