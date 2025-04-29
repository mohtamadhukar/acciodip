# utils/dip_checks.py

from robin_stocks import robinhood as r

def get_historical_prices(ticker):
    return r.stocks.get_stock_historicals(ticker, interval='day', span='week')

def check_dip(ticker):
    historical = get_historical_prices(ticker)
    highs = [float(day['high_price']) for day in historical]
    highest = max(highs)

    today_close = float(historical[-1]['close_price'])
    yesterday_close = float(historical[-2]['close_price'])
    today_change_percent = (today_close - yesterday_close) / yesterday_close * 100
    dip_percent = (highest - today_close) / highest * 100

    return dip_percent, today_change_percent