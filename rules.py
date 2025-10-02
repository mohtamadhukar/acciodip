from datetime import datetime
import logging
from typing import Dict, Optional

from state import get_event

logger = logging.getLogger(__name__)


class RuleDecision:
    def __init__(self, rule: str, dollars: float, reason: str = "", reason_code: Optional[str] = None):
        self.rule = rule
        self.dollars = dollars
        self.reason = reason
        self.reason_code = reason_code


def evaluate_crash(symbol: str, config: Dict, data: Dict) -> Optional[RuleDecision]:
    """Identify a panic 'crash' day and front-load capital accordingly.

    Business intent:
    - Detect an abrupt single-session selloff that exceeds a configured panic threshold.
    - When triggered, immediately deploy a fixed percentage of this week's buying power
      into the symbol to take advantage of extreme dislocation.

    Policy levers (from config):
    - crash.panic_threshold: minimum one-day percentage drop to qualify as a crash.
    - crash.crash_deploy_pct: fraction of the weekly budget to deploy on a crash day.
    - budgets.weekly_cap: total dollars available to allocate this week.

    Data requirements (from data):
    - closes: last two closing prices to measure the single-day move.

    Returns a RuleDecision authorizing the crash allocation when conditions are met,
    otherwise None.
    """
    strategy = config.get("crash", {})
    if not strategy:
        return None
    closes = data.get("closes", [])
    if len(closes) < 2:
        return None
    prev_close = closes[-1]
    today_close = data.get("latest_price")
    if prev_close <= 0:
        return None
    drop = (today_close - prev_close) / prev_close
    if drop <= -float(strategy.get("panic_threshold", 0.10)):
        weekly_cap = config.get("budgets", {}).get("weekly_cap", 0)
        dollars = float(weekly_cap) * float(strategy.get("crash_deploy_pct", 0.40))
        return RuleDecision("crash", dollars, reason=f"drop={drop:.2%}")
    return None


def evaluate_postcrash_drip(symbol: str, config: Dict, data: Dict) -> Optional[RuleDecision]:
    """Continue buying after a crash via a scheduled daily drip."""
    
    # Fetch active crash event and compute elapsed days
    active_crash_date = get_event(symbol)
    days_since_crash = None
    if active_crash_date:
        try:
            crash_date = datetime.strptime(active_crash_date, "%Y%m%d").date()
            days_since_crash = (datetime.now().date() - crash_date).days
        except Exception:
            days_since_crash = None
    
    
    strategy = config.get("crash", {})
    drip_days = int(strategy.get("post_crash_days", 0))
    if drip_days <= 0:
        return None

    if not active_crash_date or days_since_crash is None:
        return None
    # Start the drip the day AFTER the crash; allow through day N
    if days_since_crash < 1 or days_since_crash > drip_days:
        return None

    weekly_cap = float(config.get("budgets", {}).get("weekly_cap", 0))
    total_cap = float(strategy.get("post_crash_total_cap", 0.0)) * weekly_cap
    if total_cap <= 0:
        return None

    per_day = total_cap / drip_days
    return RuleDecision(
        "postcrash_drip",
        per_day,
        reason=f"post-crash drip day {int(days_since_crash)}/{drip_days}",
    )


def evaluate_normal(symbol: str, config: Dict, data: Dict) -> Optional[RuleDecision]:
    """Authorize routine dip-buying outside of panics using dual confirmation.

    Business intent:
    - Avoid chasing strength; only consider entries on days with at least a small
      same-day decline (gate).
    - Then require either a sizable single-day drop or a sufficient drawdown from the
      recent high to confirm a meaningful pullback.

    Policy levers (from config.normal):
    - same_day_min: minimum same-day decline to even consider buying.
    - normal_one_day: threshold for a significant one-day selloff.
    - cumulative: minimum drawdown from the recent high (peak-to-last close).
    - budgets.weekly_cap (from budgets): maximum dollars to authorize for routine dips.

    Data requirements (from data):
    - highs: recent highs to gauge cumulative drawdown.
    - closes: last two closes to compute the same-day move.

    Returns a RuleDecision with up to the weekly budget when conditions pass, otherwise
    None.
    """
    strategy = config.get("normal", {})
    highs = data.get("highs", [])
    closes = data.get("closes", [])
    if len(closes) < 2 or not highs:
        return None
    today_close = data.get("latest_price")
    prev_close = closes[-1]
    if prev_close <= 0:
        return None
    same_day_drop = (today_close - prev_close) / prev_close
    highest = max(highs)
    dip_from_peak = (highest - today_close) / highest if highest else 0
    cond_daily = same_day_drop <= -float(strategy.get("same_day_min", 0.01))
    cond_one_day = same_day_drop <= -float(strategy.get("normal_one_day", 0.03))
    cond_cum = dip_from_peak >= float(strategy.get("cumulative", 0.05))
    if cond_daily and (cond_one_day or cond_cum):
        weekly_cap = float(config.get("budgets", {}).get("weekly_cap", 0))
        return RuleDecision("normal", weekly_cap, reason=f"drop={same_day_drop:.2%}, peak_dip={dip_from_peak:.2%}")
    return None


def select_decision(symbol: str, config: Dict, data: Dict, mode: str) -> Optional[RuleDecision]:
    decision = evaluate_crash(symbol, config, data)
    if decision: 
        return decision
    if mode == "post_crash_drip":
        decision = evaluate_postcrash_drip(symbol, config, data)
        if decision: 
            return decision
    if mode == "eod":
        decision = evaluate_normal(symbol, config, data)
        if decision: 
            return decision
    return None


