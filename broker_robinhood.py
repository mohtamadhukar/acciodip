import logging
import os
from typing import Optional, Dict

from dotenv import load_dotenv
from robin_stocks import robinhood as r

logger = logging.getLogger(__name__)


class RobinhoodBroker:
    def __init__(self, dry_run: bool = True, limit_band_bps: int = 20):
        self.dry_run = dry_run
        self.limit_band_bps = limit_band_bps

    def login(self, username: Optional[str] = None, password: Optional[str] = None, mfa_code: Optional[str] = None) -> None:
        load_dotenv()
        username = username or os.getenv("RH_USERNAME")
        password = password or os.getenv("RH_PASSWORD")
        if not username or not password:
            raise ValueError("Missing RH_USERNAME/RH_PASSWORD")
        r.login(username=username, password=password, mfa_code=mfa_code)

    def logout(self) -> None:
        r.logout()

    def get_cash_balance(self) -> float:
        profile = r.profiles.load_account_profile()
        return float(profile.get("portfolio_cash", 0) or 0)

    def get_latest_price(self, symbol: str) -> float:
        price = r.stocks.get_latest_price(symbol)
        return float(price[0]) if price else 0.0

    def place_limit_buy_dollars(self, symbol: str, dollars: float) -> Optional[Dict]:
        if self.dry_run:
            return {"status": "simulated", "symbol": symbol, "notional": dollars}
        last = self.get_latest_price(symbol)
        limit_price = round(last * (1 + self.limit_band_bps / 10000), 2)
        qty = max(0.0001, round(dollars / limit_price, 6))
        return r.orders.order_buy_limit(symbol, qty, limit_price)


