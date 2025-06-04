# utils/dip_checks.py

import yfinance as yf
from datetime import datetime, timedelta

def get_historical_prices(ticker):
    # Get data for the last week
    stock = yf.Ticker(ticker)
    end_date = datetime.now()
    start_date = end_date - timedelta(days=7)
    historical = stock.history(start=start_date, end=end_date, interval='1d')
    return historical

def check_dip(ticker):
    historical = get_historical_prices(ticker)
    highs = historical['High'].tolist()
    highest = max(highs)

    today_close = historical['Close'].iloc[-1]
    yesterday_close = historical['Close'].iloc[-2]
    today_change_percent = (today_close - yesterday_close) / yesterday_close * 100
    dip_percent = (highest - today_close) / highest * 100

    return dip_percent, today_change_percent