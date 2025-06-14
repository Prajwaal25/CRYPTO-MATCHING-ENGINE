
from order import Order
from order_book import OrderBook

def test_limit_order_matching():
    ob = OrderBook("BTC-USDT")
    o1 = Order("BTC-USDT", "sell", "limit", 1, 100)
    o2 = Order("BTC-USDT", "buy", "limit", 1, 100)
    ob.add_order(o1)
    trades = ob.add_order(o2)
    assert len(trades) == 1
    assert trades[0][2] == 100
