🚀 Cryptocurrency Matching Engine

A high-performance, REG NMS-inspired crypto matching engine built with Python & FastAPI.
Supports real-time WebSocket feeds, core and advanced order types (Stop, IOC, FOK), persistence, maker-taker fee model, and live market data dashboard with CSV export.

---

🧠 System Architecture

**Modules**:
- `main.py`: FastAPI REST and WebSocket app
- `engine.py`: Core matching logic
- `order_book.py`: FIFO price-level book
- `stop_orders.py`: Async monitor for conditional orders
- `trade_log.py`: JSONL-based trade log
- `models.py`: Pydantic schemas
- `persistence_utils.py`: Order book save/load
- `templates/`: UI dashboard at `/test`
- `static/`: Dark mode UI JS + CSS

**Flow**:
- Orders submitted → processed by `MatchingEngine`
- Trades matched, logged, and broadcast via WebSocket
- Order book updated and streamed to subscribers

---

📦 Features

- ✅ Price-Time Priority Matching
- ✅ Market, Limit, IOC, FOK
- ✅ Stop-Loss, Stop-Limit
- ✅ Real-Time BBO + Order Book Depth
- ✅ Trade Execution Feed
- ✅ Trade-through Protection (REG NMS)
- ✅ Maker-Taker Fee Model
- ✅ Order Book Persistence
- ✅ Inline UI Dashboard (`/test`)
- ✅ CSV Export & Dark Mode

---

🧾 API Specification

🔹 Core

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/submit_order` | POST | Submit core orders |
| `/submit_stop_order` | POST | Submit conditional stop/limit |
| `/orderbook/{symbol}` | GET | Top 10 level book snapshot |
| `/bbo/{symbol}` | GET | Best Bid/Offer |
| `/trades/{symbol}` | GET | Recent trades |
| `/health` | GET | Status check |
| `/` | GET | Engine info |
| `/test` | GET | Interactive UI |

🔹 WebSockets

| Endpoint | Type | Purpose |
|----------|------|---------|
| `/ws/market_data/{symbol}` | WebSocket | Live book updates |
| `/ws/trades` | WebSocket | Real-time trade executions |

---

🔍 Matching Logic

- Price-time priority enforced
- No internal trade-throughs
- FIFO queue at each price level
- Market orders matched immediately
- IOC: cancel remainder if not instantly filled
- FOK: fill completely or cancel
- Stop orders: monitored via async background task

---

## 💰 Fee Model

- **Maker fee**: 0.01% (adds resting liquidity)
- **Taker fee**: 0.02% (removes liquidity)
- Fees shown in each trade object:
  ```json
  {
    "price": 30000,
    "quantity": 1,
    "maker_fee": 3,
    "taker_fee": 6
  }


 Bonus Section Features

This project goes beyond core functionality by implementing several advanced capabilities:

1. Advanced Order Types
- Stop-Loss: Triggers a market/limit order when price crosses a threshold.
- Stop-Limit: Triggers a limit order once price hits a set level.
- Take-Profit: Alias to stop-limit with upward trigger for exits.

→ Handled via `/submit_stop_order` and monitored asynchronously in the background.

2. Order Book Persistence
- Order book state is automatically saved on shutdown and loaded on restart.
- File-based persistence using JSON ensures fault recovery.
- Implemented via `persistence_utils.py`.

3. Concurrency & Performance Optimization
- Used `asyncio` for:
  - WebSocket market data updates
  - Background stop order monitoring
  - BBO/trade broadcasting
- Benchmarks captured using `time.perf_counter()`.

📈 Sample Latencies
| Operation             | Avg Latency |
|----------------------|-------------|
| Order Matching        | ~1.2 ms     |
| BBO Update            | ~0.4 ms     |
| Trade WebSocket Push  | ~0.9 ms     |


4. Maker-Taker Fee Model
- Taker: 0.02% fee (market order or IOC/FOK)
- Maker: 0.01% fee (resting order)
- Fee included in trade execution reports:
  ```json
  {
    "maker_fee": 3.0,
    "taker_fee": 6.0
  }
