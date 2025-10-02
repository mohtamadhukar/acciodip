# utils/dip_checks.py

from utils.robinhood_api import get_stock_historicals

def check_dip(ticker):
    # Fetch last week of daily candles from Robinhood
    candles = get_stock_historicals(ticker, span='week', interval='day')
    if not candles or len(candles) < 2:
        return 0.0, 0.0

    highs = [float(c['high_price']) for c in candles]
    closes = [float(c['close_price']) for c in candles]

    highest = max(highs)
    today_close = closes[-1]
    yesterday_close = closes[-2]

    if yesterday_close == 0:
        return 0.0, 0.0

    today_change_percent = (today_close - yesterday_close) / yesterday_close * 100
    dip_percent = (highest - today_close) / highest * 100 if highest else 0.0

    return dip_percent, today_change_percent