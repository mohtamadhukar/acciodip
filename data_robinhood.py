import logging
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Optional, Tuple

from robin_stocks import robinhood as r

logger = logging.getLogger(__name__)


def get_quote(symbol: str) -> Optional[Dict]:
    q = r.stocks.get_quotes(symbol)
    return q[0] if q else None


def get_latest_trade_ts(symbol: str) -> Optional[datetime]:
    q = get_quote(symbol)
    if not q:
        return None
    ts = q.get("updated_at") or q.get("last_trade_price_source")
    if not ts:
        return None
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00")).astimezone(timezone.utc)
    except Exception:
        return None


def get_historicals(symbol: str, span: str = "week", interval: str = "day") -> List[Dict]:
    data = r.stocks.get_stock_historicals(symbol, interval=interval, span=span, bounds='regular')
    return data or []

def get_latest_price(symbol: str) -> float:
    price = r.stocks.get_latest_price(symbol)
    return float(price[0]) if price else 0.0

def compute_recent_peak_close(closes: List[float]) -> float:
    return max(closes) if closes else 0.0


def parse_duration_to_timedelta(spec: str) -> timedelta:
    spec = (spec or "").strip().lower()
    if spec.endswith("ms"):
        return timedelta(milliseconds=int(spec[:-2] or 0))
    if spec.endswith("s"):
        return timedelta(seconds=int(spec[:-1] or 0))
    if spec.endswith("m"):
        return timedelta(minutes=int(spec[:-1] or 0))
    if spec.endswith("h"):
        return timedelta(hours=int(spec[:-1] or 0))
    if spec.endswith("d"):
        return timedelta(days=int(spec[:-1] or 0))
    # default minutes
    try:
        return timedelta(minutes=int(spec))
    except Exception:
        return timedelta(minutes=3)


def is_quote_stale(symbol: str, max_age_spec: str) -> Tuple[bool, Optional[datetime]]:
    last_ts = get_latest_trade_ts(symbol)
    if not last_ts:
        return True, None
    max_age = parse_duration_to_timedelta(max_age_spec)
    now = datetime.now(timezone.utc)
    return (now - last_ts) > max_age, last_ts


