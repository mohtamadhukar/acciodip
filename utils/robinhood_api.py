import logging

import pyotp
from robin_stocks import robinhood as r
import datetime

logger = logging.getLogger(__name__)

def generate_totp(mfa_key):
    """
    Generates a TOTP code using the provided MFA key.
    """
    totp = pyotp.TOTP(mfa_key).now()
    logger.info("🍺 Generated TOTP (MFA PIN)")
    return totp


def login_robinhood(username, password, mfa_key):
    """
    Logs into Robinhood using credentials and a required MFA TOTP.
    """
    # totp = generate_totp(mfa_key)

    try:
        logger.info("🍺 Attempting to log in to Robinhood...")
        # login_response = r.login(
        #     username=username,
        #     password=password,
        #     store_session=False,
        #     mfa_code=totp
        # )
        login_response = r.authentication.login(username=username, password=password, by_sms=True)

        if isinstance(login_response, dict) and "access_token" in login_response:
            logger.info("🍺 Successfully logged into Robinhood")
        else:
            detail = login_response.get("detail", "No details provided.")
            logger.error(f"❌ Login failed: {detail}")
            raise ValueError(f"❌ Login failed: {detail}")
    except Exception as e:
        logger.error(f"❌ Exception during login: {e}")
        raise

def logout_robinhood():
    """
    Logout.
    """
    r.logout()

def get_cash_balance():
    """
    Get available cash.
    """
    profile = r.profiles.load_account_profile()
    return float(profile['buying_power'])

def get_latest_price(ticker):
    """
    Get latest ETF price.
    """
    return float(r.stocks.get_latest_price(ticker)[0])

def place_market_buy(ticker, quantity):
    """
    Place a market buy order.
    """
    r.orders.order_buy_market(ticker, quantity)

def get_recent_orders(ticker):
    """
    Fetch recent buy orders for ETF.
    """
    orders = r.orders.get_all_stock_orders()
    relevant = []
    one_week = datetime.datetime.now() - datetime.timedelta(days=7)

    for order in orders:
        if order['state'] == 'filled' and ticker.lower() in order['instrument'].lower():
            updated = datetime.datetime.strptime(order['updated_at'], "%Y-%m-%dT%H:%M:%S.%fZ")
            if updated > one_week:
                relevant.append({'date': updated.strftime('%Y-%m-%d'), 'tag': classify_order(order)})

    return relevant

def get_weekly_spent(ticker):
    """
    Calculate how much money was spent buying ticker this week.
    """
    orders = get_recent_orders(ticker)
    total = 0
    for order in orders:
        if 'price' in order:
            total += float(order['price'])
    return total

def classify_order(order):
    """
    Tag order type (normal or crash-day).
    """
    return 'crash_day_buy' if float(order['cumulative_notional']['amount']) > 300 else 'normal_buy'