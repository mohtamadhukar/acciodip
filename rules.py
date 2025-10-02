import logging
from typing import Dict, Optional

logger = logging.getLogger(__name__)


class RuleDecision:
    def __init__(self, rule: str, dollars: float, reason: str = "", reason_code: Optional[str] = None):
        self.rule = rule
        self.dollars = dollars
        self.reason = reason
        self.reason_code = reason_code


def evaluate_crash(symbol: str, config: Dict, data: Dict) -> Optional[RuleDecision]:
    strategy = config.get("crash", {})
    if not strategy:
        return None
    closes = data.get("closes", [])
    if len(closes) < 2:
        return None
    prev_close = closes[-2]
    today_close = closes[-1]
    if prev_close <= 0:
        return None
    drop = (today_close - prev_close) / prev_close
    if drop <= -float(strategy.get("panic_threshold", 0.10)):
        weekly_cap = config.get("budgets", {}).get("weekly_cap", 0)
        dollars = float(weekly_cap) * float(strategy.get("crash_deploy_pct", 0.40))
        return RuleDecision("crash", dollars, reason=f"drop={drop:.2%}")
    return None


def evaluate_postcrash_drip(symbol: str, config: Dict, data: Dict) -> Optional[RuleDecision]:
    strategy = config.get("crash", {})
    drip_days = int(strategy.get("post_crash_days", 0))
    if drip_days <= 0:
        return None
    weekly_cap = float(config.get("budgets", {}).get("weekly_cap", 0))
    total_cap = float(strategy.get("post_crash_total_cap", 0.0)) * weekly_cap
    if total_cap <= 0:
        return None
    per_day = total_cap / drip_days
    return RuleDecision("postcrash_drip", per_day, reason="post-crash drip")


def evaluate_normal(symbol: str, config: Dict, data: Dict) -> Optional[RuleDecision]:
    strategy = config.get("normal", {})
    highs = data.get("highs", [])
    closes = data.get("closes", [])
    if len(closes) < 2 or not highs:
        return None
    today_close = closes[-1]
    prev_close = closes[-2]
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


def select_decision(symbol: str, config: Dict, data: Dict) -> Optional[RuleDecision]:
    decision = evaluate_crash(symbol, config, data)
    if decision:
        return decision
    decision = evaluate_postcrash_drip(symbol, config, data)
    if decision:
        return decision
    decision = evaluate_normal(symbol, config, data)
    return decision


