from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
import asyncio
import json
import logging
import uuid
from typing import List, Dict, Set
from datetime import datetime
from persistence_utils import save_order_book_state, load_order_book_state
from models import Order, OrderResponse, L2Snapshot, BBO, Trade
from engine import MatchingEngine
from trade_log import get_recent_trades, trade_history
from stop_orders import add_stop_order, monitor_stop_orders

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("FastAPI")

# Initialize FastAPI app
app = FastAPI(
    title="Cryptocurrency Matching Engine",
    description="High-performance REG NMS-inspired matching engine with real-time data streaming",
    version="1.0.0"
)

# Initialize matching engine
engine = MatchingEngine()

from stop_orders import set_engine
set_engine(engine)

# WebSocket connection management
class ConnectionManager:
    
    def __init__(self):
        self.market_data_connections: Dict[str, List[WebSocket]] = {}  # symbol -> [websockets]
        self.trade_connections: List[WebSocket] = []
        
    async def connect_market_data(self, websocket: WebSocket, symbol: str):
        await websocket.accept()
        if symbol not in self.market_data_connections:
            self.market_data_connections[symbol] = []
        self.market_data_connections[symbol].append(websocket)
        logger.info(f"Market data client connected for {symbol}")
        
    async def connect_trades(self, websocket: WebSocket):
        await websocket.accept()
        self.trade_connections.append(websocket)
        logger.info("Trade data client connected")
        
    def disconnect_market_data(self, websocket: WebSocket, symbol: str):
        if symbol in self.market_data_connections:
            if websocket in self.market_data_connections[symbol]:
                self.market_data_connections[symbol].remove(websocket)
        logger.info(f"Market data client disconnected for {symbol}")
        
    def disconnect_trades(self, websocket: WebSocket):
        if websocket in self.trade_connections:
            self.trade_connections.remove(websocket)
        logger.info("Trade data client disconnected")
        
    async def broadcast_market_data(self, symbol: str):
        """Broadcast market data update for a symbol"""
        if symbol not in self.market_data_connections:
            return
            
        # Get current market data
        bbo = engine.get_bbo(symbol)
        depth = engine.get_order_book_depth(symbol)
        
        snapshot = L2Snapshot(
            symbol=symbol,
            bids=depth["bids"],
            asks=depth["asks"]
        )
        
        # Send to all connected clients for this symbol
        disconnected = []
        for websocket in self.market_data_connections[symbol]:
            try:
                await websocket.send_text(snapshot.json())
            except:
                disconnected.append(websocket)
                
        # Clean up disconnected clients
        for ws in disconnected:
            self.disconnect_market_data(ws, symbol)
            
    async def broadcast_trade(self, trade: Trade):
        """Broadcast trade execution to all connected clients"""
        if not self.trade_connections:
            return
            
        disconnected = []
        for websocket in self.trade_connections:
            try:
                await websocket.send_text(trade.json())
            except:
                disconnected.append(websocket)
                
        # Clean up disconnected clients
        for ws in disconnected:
            self.disconnect_trades(ws)

# Initialize connection manager
connection_manager = ConnectionManager()

# REST API Endpoints
@app.post("/submit_order", response_model=OrderResponse)
async def submit_order(order: Order):
    """Submit a new order to the matching engine"""
    try:
        # Validate required price for non-market orders
        if order.order_type != "market" and order.price is None:
            raise HTTPException(status_code=400, detail="Price required for non-market orders")

        # Generate UUID and timestamp if not provided
        if not hasattr(order, 'id') or order.id is None:
            order.id = uuid.uuid4()

        # Process the order
        trades = engine.process_order(order)

        # Broadcast market data update
        await connection_manager.broadcast_market_data(order.symbol)

        # Broadcast trade executions
        for trade in trades:
            await connection_manager.broadcast_trade(trade)

        return OrderResponse(order_id=order.id, trades=len(trades))

    except Exception as e:
        logger.error(f"Error processing order: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@app.get("/orderbook/{symbol}")
async def get_order_book(symbol: str):
    """Get order book snapshot for a symbol"""
    try:
        depth = engine.get_order_book_depth(symbol)
        if not depth["bids"] and not depth["asks"]:
            return JSONResponse(status_code=404, content={"error": "Symbol not found or no orders"})
        
        snapshot = L2Snapshot(
            symbol=symbol,
            bids=depth["bids"],
            asks=depth["asks"]
        )
        return snapshot.dict()
        
    except Exception as e:
        logger.error(f"Error getting order book for {symbol}: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

@app.get("/bbo/{symbol}")
async def get_bbo_endpoint(symbol: str):
    """Get best bid/offer for a symbol"""
    try:
        bbo = engine.get_bbo(symbol)
        if bbo["bid"] is None and bbo["ask"] is None:
            return JSONResponse(status_code=404, content={"error": "Symbol not found or no orders"})
        
        return BBO(
            symbol=symbol,
            bid=bbo["bid"], 
            ask=bbo["ask"]
        ).dict()
        
    except Exception as e:
        logger.error(f"Error getting BBO for {symbol}: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

@app.get("/trades/{symbol}")
async def get_recent_trades_endpoint(symbol: str, limit: int = 20):
    """Get recent trades for a symbol"""
    try:
        trades = get_recent_trades(symbol, limit)
        return {"symbol": symbol, "trades": [trade.dict() for trade in trades]}
        
    except Exception as e:
        logger.error(f"Error getting trades for {symbol}: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "total_trades": len(trade_history)
    }

@app.get("/")
async def get_dashboard():
    """Dashboard endpoint"""
    return {"message": "Crypto Matching Engine Dashboard", "status": "running"}

# WebSocket Endpoints
@app.websocket("/ws/market_data/{symbol}")
async def market_data_websocket(websocket: WebSocket, symbol: str):
    """WebSocket endpoint for real-time market data"""
    await connection_manager.connect_market_data(websocket, symbol)
    
    try:
        # Send initial snapshot
        await connection_manager.broadcast_market_data(symbol)
        
        # Keep connection alive and handle client messages
        while True:
            try:
                data = await websocket.receive_text()
                # Handle any client commands if needed
                message = json.loads(data)
                if message.get("type") == "ping":
                    await websocket.send_text(json.dumps({"type": "pong"}))
            except asyncio.TimeoutError:
                # Send periodic heartbeat
                await websocket.send_text(json.dumps({
                    "type": "heartbeat",
                    "timestamp": datetime.utcnow().isoformat()
                }))
            except Exception as e:
                logger.error(f"Error in market data websocket: {str(e)}")
                break
                
    except WebSocketDisconnect:
        connection_manager.disconnect_market_data(websocket, symbol)
    except Exception as e:
        logger.error(f"Unexpected error in market data websocket: {str(e)}")
        connection_manager.disconnect_market_data(websocket, symbol)

@app.websocket("/ws/trades")
async def trades_websocket(websocket: WebSocket):
    """WebSocket endpoint for real-time trade executions"""
    await connection_manager.connect_trades(websocket)
    
    try:
        # Keep connection alive and handle client messages
        while True:
            try:
                data = await websocket.receive_text()
                message = json.loads(data)
                if message.get("type") == "ping":
                    await websocket.send_text(json.dumps({"type": "pong"}))
            except asyncio.TimeoutError:
                # Send periodic heartbeat
                await websocket.send_text(json.dumps({
                    "type": "heartbeat",
                    "timestamp": datetime.utcnow().isoformat()
                }))
            except Exception as e:
                logger.error(f"Error in trades websocket: {str(e)}")
                break
                
    except WebSocketDisconnect:
        connection_manager.disconnect_trades(websocket)
    except Exception as e:
        logger.error(f"Unexpected error in trades websocket: {str(e)}")
        connection_manager.disconnect_trades(websocket)

@app.get("/test", response_class=HTMLResponse)
async def get_test_page():
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Crypto Matching Engine - Inline UI</title>
        <style>
            body {
                background-color: #121212;
                color: #f5f5f5;
                font-family: Arial, sans-serif;
                margin: 0;
                padding: 20px;
            }
            .container {
                max-width: 900px;
                margin: auto;
            }
            .section {
                margin: 20px 0;
                padding: 20px;
                background: #1e1e1e;
                border-radius: 10px;
                box-shadow: 0 0 10px rgba(0,0,0,0.3);
            }
            input, select, button {
                margin: 5px;
                padding: 10px;
                font-size: 16px;
            }
            #output {
                background: #222;
                padding: 10px;
                height: 300px;
                overflow-y: auto;
                font-family: monospace;
                border-radius: 5px;
            }
            .floating-log {
                position: fixed;
                bottom: 20px;
                right: 20px;
                width: 300px;
                height: 200px;
                background: #1e1e1e;
                border: 1px solid #333;
                overflow-y: auto;
                padding: 10px;
                font-size: 14px;
                border-radius: 8px;
            }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>💱 Crypto Matching Engine </h1>

            <div class="section">
                <h3>📡 Market Data WebSocket</h3>
                <button onclick="connectMarketData()">Connect BTC-USDT</button>
                <button onclick="disconnectMarketData()">Disconnect</button>
            </div>

            <div class="section">
                <h3>📝 Submit Order</h3>
                <input type="text" id="symbol" placeholder="Symbol" value="BTC-USDT">
                <select id="side">
                    <option value="buy">Buy</option>
                    <option value="sell">Sell</option>
                </select>
                <select id="orderType">
                    <option value="limit">Limit</option>
                    <option value="market">Market</option>
                </select>
                <input type="number" id="quantity" placeholder="Quantity" value="1">
                <input type="number" id="price" placeholder="Price" value="30000">
                <button onclick="submitOrder()">Submit Order</button>
            </div>

            <div class="section">
                <h3>🧾 Output</h3>
                <div id="output"></div>
            </div>
        </div>

        <div class="floating-log" id="tradeLog">
            <b>📈 Live Trade Log</b>
            <div id="logContent"></div>
        </div>

        <script>
            let marketDataWs = null;

            function log(message) {
                const output = document.getElementById('output');
                output.innerHTML += new Date().toLocaleTimeString() + ': ' + message + '<br>';
                output.scrollTop = output.scrollHeight;

                const logBox = document.getElementById('logContent');
                logBox.innerHTML = new Date().toLocaleTimeString() + ' ▶ ' + message + '<br>' + logBox.innerHTML;
            }

            function connectMarketData() {
                if (marketDataWs) marketDataWs.close();
                marketDataWs = new WebSocket('ws://localhost:8000/ws/market_data/BTC-USDT');
                marketDataWs.onopen = () => log('✅ WebSocket connected');
                marketDataWs.onmessage = (event) => {
                    const data = JSON.parse(event.data);
                    log('Market: ' + JSON.stringify(data));
                };
                marketDataWs.onclose = () => log('🔌 WebSocket disconnected');
            }

            function disconnectMarketData() {
                if (marketDataWs) {
                    marketDataWs.close();
                    marketDataWs = null;
                }
            }

            async function submitOrder() {
                const order = {
                    symbol: document.getElementById('symbol').value,
                    side: document.getElementById('side').value,
                    order_type: document.getElementById('orderType').value,
                    quantity: parseFloat(document.getElementById('quantity').value),
                };
                if (order.order_type === 'limit') {
                    order.price = parseFloat(document.getElementById('price').value);
                }
                try {
                    const res = await fetch('/submit_order', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify(order)
                    });
                    const result = await res.json();
                    log('📤 Order submitted: ' + JSON.stringify(result));
                } catch (err) {
                    log('❌ Error: ' + err.message);
                }
            }
        </script>
    </body>
    </html>
    """

@app.post("/submit_stop_order", response_model=OrderResponse)
async def submit_stop_order(order: Order):
    """Accepts a stop/conditional order"""
    if not order.trigger_price or not order.trigger_type:
        raise HTTPException(status_code=400, detail="trigger_price and trigger_type required for stop orders")

    if order.order_type not in ["limit", "market"]:
        raise HTTPException(status_code=400, detail="Only limit or market type supported for stop/triggered execution")

    add_stop_order(order)
    return OrderResponse(order_id=order.id, trades=0, status="queued")

@app.on_event("startup")
async def start_background_tasks():
    asyncio.create_task(monitor_stop_orders())

@app.on_event("startup")
async def startup():
    load_order_book_state(engine.order_books, engine)
    asyncio.create_task(monitor_stop_orders())

@app.on_event("shutdown")
def shutdown():
    save_order_book_state(engine.order_books)

# Optional: To run locally for testing
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)