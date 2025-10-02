import logging
import os
from datetime import datetime, timezone, timedelta
from typing import Dict

from utils.config_loader import load_config
from broker_robinhood import RobinhoodBroker
from data_robinhood import get_historicals
from rules import select_decision
from state import insert_decision, upsert_event, get_event, has_decision, sum_spent
from data_robinhood import get_quote, is_quote_stale

logger = logging.getLogger(__name__)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _build_data_bundle(symbol: str) -> Dict:
    candles = get_historicals(symbol, span="week", interval="day")
    closes = [float(c.get("close_price", 0) or 0) for c in candles]
    highs = [float(c.get("high_price", 0) or 0) for c in candles]
    data = {
        "candles": candles,
        "closes": closes,
        "highs": highs,
    }
    return data


def _place_and_record(broker: RobinhoodBroker, symbol: str, dollars: float, decision_row: Dict) -> None:
    try:
        order = broker.place_limit_buy_dollars(symbol, dollars)
        decision_row["broker_order_id"] = (order or {}).get("id") or (order or {}).get("order_id")
        decision_row["filled_qty"] = None
        decision_row["filled_avg_price"] = None
        insert_decision(decision_row)
    except Exception as exc:
        logger.exception("Order placement failed: %s", exc)
        decision_row["status"] = "skipped"
        decision_row["reason_code"] = "ORDER_ERROR"
        decision_row["reason"] = str(exc)
        insert_decision(decision_row)


def _run_once(mode: str) -> None:
    config = load_config()
    guardrails = (config or {}).get("guardrails", {})
    etfs = (config or {}).get("etfs", {}) or {}

    dry_run = os.getenv("DRY_RUN", "true").lower() == "true"
    limit_band_bps = int(guardrails.get("order_limit_band_bps", 20))
    broker = RobinhoodBroker(dry_run=dry_run, limit_band_bps=limit_band_bps)
    broker.login()

    try:
        for symbol, etf_cfg in etfs.items():
            data = _build_data_bundle(symbol)
            strategy_cfg = etf_cfg.get("strategy", {})
            decision = select_decision(
                symbol=symbol, 
                config=strategy_cfg, 
                data=data,
                mode=mode,
            )
            if not decision:
                continue

            today_str = datetime.now().strftime("%Y%m%d")
            if decision.rule == "crash":
                id_key = f"{today_str}-crash-{today_str}"
                upsert_event(symbol, active_crash_date=today_str)
            elif decision.rule == "postcrash_drip":
                id_key = f"{today_str}-postcrash_drip-{today_str}"
            else:
                id_key = f"{today_str}-normal-none"

            if has_decision(id_key):
                continue

            budgets = (etf_cfg or {}).get("budgets", {})
            min_trade = float(guardrails.get("min_trade", 0))
            max_trade = float(guardrails.get("max_trade", float('inf')))
            agg = (guardrails or {}).get("aggregate_limits", {})

            now = datetime.now()
            week_start = (now - timedelta(days=now.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)
            next_week = week_start + timedelta(days=7)
            month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            next_month = (month_start.replace(day=28) + timedelta(days=4)).replace(day=1)

            spent_week_symbol = sum_spent(symbol, week_start.isoformat(), next_week.isoformat())
            spent_week_all = sum_spent(None, week_start.isoformat(), next_week.isoformat())
            spent_month_all = sum_spent(None, month_start.isoformat(), next_month.isoformat())

            weekly_cap_symbol = float(budgets.get("weekly_cap", float('inf')))
            monthly_cap_symbol = float(budgets.get("monthly_cap", float('inf')))
            weekly_cap_all = float(agg.get("weekly_total_cap", float('inf')))
            monthly_cap_all = float(agg.get("monthly_total_cap", float('inf')))

            # Start with the dollars the rule *wanted* to invest for this trade
            dollars = float(decision.dollars)

            # Apply budget guardrails in order:
            # 1. Per-symbol weekly cap:
            #    Don't spend more than this ETF's weekly_cap minus what’s already spent this week.
            dollars = min(dollars, max(0.0, weekly_cap_symbol - spent_week_symbol))

            # 2. Global weekly cap (all ETFs combined):
            #    Clamp to what’s left of the total weekly_cap across all ETFs.
            dollars = min(dollars, max(0.0, weekly_cap_all - spent_week_all))

            # 3. Per-symbol monthly cap:
            #    Clamp to what’s left of this ETF's monthly_cap after current month’s spend.
            dollars = min(dollars, max(0.0, monthly_cap_symbol - sum_spent(symbol, month_start.isoformat(), next_month.isoformat())))

            # 4. Global monthly cap (all ETFs combined):
            #    Finally, clamp to what’s left of the total monthly_cap across all ETFs.
            dollars = min(dollars, max(0.0, monthly_cap_all - spent_month_all))

            # After all these checks, "dollars" is the FINAL trade size allowed,guaranteed not to breach weekly/monthly caps per ETF or across all ETFs.

            # Cash reserve floor
            cash = broker.get_cash_balance()
            reserve_floor = float(budgets.get("cash_reserve_floor", 0))
            if reserve_floor > 0 and cash > 0:
                max_affordable = max(0.0, cash * (1 - reserve_floor))
                dollars = min(dollars, max_affordable)

            dollars = max(0.0, min(max_trade, dollars))
            if dollars < min_trade:
                row = {
                    "idempotency_key": id_key,
                    "ts": _now_iso(),
                    "rule": decision.rule,
                    "symbol": symbol,
                    "dollars": float(dollars),
                    "status": "skipped",
                    "reason": "Below min_trade after clamps",
                    "reason_code": "MIN_TRADE",
                    "broker_order_id": None,
                    "filled_qty": None,
                    "filled_avg_price": None,
                }
                insert_decision(row)
                continue

            row = {
                "idempotency_key": id_key,
                "ts": _now_iso(),
                "rule": decision.rule,
                "symbol": symbol,
                "dollars": float(dollars),
                "status": "placed",
                "reason": decision.reason,
                "reason_code": decision.reason_code,
                "broker_order_id": None,
                "filled_qty": None,
                "filled_avg_price": None,
            }

            _place_and_record(broker, symbol, dollars, row)
    finally:
        broker.logout()


def run_rth() -> None:
    _run_once("rth")


def run_drip() -> None:
    _run_once("post_crash_drip")


def run_eod() -> None:
    _run_once("eod")


