# services/dip_buyer.py

"""
Unified Dip Buyer
Handles dip detection, crash detection, and post-crash staged buying for all ETFs.
"""

import logging
from utils.config_loader import load_config
from utils.robinhood_api import *
from utils.dip_checks import check_dip
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)
CONFIG = load_config()

def run():
    """
    Main service runner: handles all ETFs.
    """
    login_robinhood(username='mohta.madhukar@gmail.com', password='#1dinkarvatsalM', mfa_key="R2VEYSMKSW75DVU7")

    for ticker, etf_settings in CONFIG['etfs'].items():
        logger.info(f"📈 Checking {ticker}...")

        cash = get_cash_balance()
        current_week_spend = get_weekly_spent(ticker)
        dip_percent, today_change_percent = check_dip(ticker)
        recent_orders = get_recent_orders(ticker)

        # Check if crash detected
        if today_change_percent <= -etf_settings['panic_drop_threshold']:
            logger.warning(f"🚨 Crash detected for {ticker} ({today_change_percent:.2f}% drop)!")
            handle_crash_buy(ticker, etf_settings, cash, current_week_spend)

        # Check if post-crash mode active
        elif is_in_post_crash_mode(recent_orders, etf_settings):
            logger.info(f"🛡️ Post-crash mode active for {ticker}. Doing staged buy.")
            handle_post_crash_staged_buy(ticker, etf_settings, cash, current_week_spend)

        # Normal dip check
        elif dip_percent >= etf_settings['dip_threshold_percent'] and today_change_percent <= -etf_settings['today_drop_threshold']:
            logger.info(f"📉 Dip detected for {ticker} ({dip_percent:.2f}% from high).")
            handle_normal_dip_buy(ticker, etf_settings, cash, current_week_spend)

    logout_robinhood()

def handle_crash_buy(ticker, etf_settings, cash, weekly_spend):
    """
    Handle immediate crash-day buying logic.
    """
    buy_amount = (etf_settings['weekly_limit'] * etf_settings['crash_day_buy_percent']) / 100
    invest(ticker, min(buy_amount, available_to_invest(cash, weekly_spend, etf_settings)))

def handle_post_crash_staged_buy(ticker, etf_settings, cash, weekly_spend):
    """
    Handle staged buys during post-crash mode.
    """
    invest(ticker, min(etf_settings['post_crash_buy_amount'], available_to_invest(cash, weekly_spend, etf_settings)))

def handle_normal_dip_buy(ticker, etf_settings, cash, weekly_spend):
    """
    Handle normal dip buying logic.
    """
    invest(ticker, available_to_invest(cash, weekly_spend, etf_settings))

def available_to_invest(cash, weekly_spend, etf_settings):
    """
    Calculate safe amount to invest.
    """
    available_budget = etf_settings['weekly_limit'] - weekly_spend
    return max(0, min(available_budget, cash - CONFIG['general']['min_cash_reserve']))

def invest(ticker, dollars):
    """
    Execute market buy order.
    """
    if dollars <= 0:
        logger.info(f"💤 No buying power left for {ticker}.")
        return
    price = get_latest_price(ticker)
    quantity = round(dollars / price, 4)
    place_market_buy(ticker, quantity)
    logger.info(f"🛒 Bought {quantity} shares of {ticker} (${dollars:.2f}).")

def is_in_post_crash_mode(orders, etf_settings):
    """
    Check if ETF is still inside post-crash staged buy window (days since crash).
    """
    crash_orders = [o for o in orders if o['tag'] == 'crash_day_buy']
    if crash_orders:
        last_crash = datetime.strptime(crash_orders[-1]['date'], "%Y-%m-%d")
        days_since_crash = (datetime.now() - last_crash).days
        return days_since_crash < etf_settings['post_crash_days']
    return False