import logging
from datetime import datetime, timezone
from typing import Dict

from utils.config_loader import load_config
from state import get_conn

logger = logging.getLogger(__name__)


def run_weekly_measurement() -> None:
    config = load_config()
    etfs = (config or {}).get("etfs", {})
    now = datetime.now(timezone.utc)
    week_ending = now.date().isoformat()

    with get_conn() as conn:
        for symbol, etf_cfg in etfs.items():
            cur = conn.execute(
                "SELECT COALESCE(SUM(dollars),0), COUNT(1) FROM decisions WHERE symbol=? AND status='placed'",
                (symbol,),
            )
            tot_dollars, buy_count = cur.fetchone()
            conn.execute(
                """
                INSERT OR REPLACE INTO metrics_weekly(
                  week_ending, symbol, bot_portfolio_value, dca_portfolio_value,
                  bot_total_invested, dca_total_invested, bot_avg_buy_price, dca_avg_buy_price,
                  bot_buy_count_to_date, dca_buy_count_to_date, bot_max_drawdown_to_date,
                  regime_stats_json, dca_weekly_cap, dca_buy_day, dca_buy_time, computed_at
                ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    week_ending,
                    symbol,
                    float(tot_dollars),
                    0.0,
                    float(tot_dollars),
                    0.0,
                    None,
                    None,
                    int(buy_count),
                    0,
                    None,
                    None,
                    float(etf_cfg.get("measurement", {}).get("dca_weekly_cap", 0)),
                    str(etf_cfg.get("measurement", {}).get("dca_buy_day", "MON")),
                    str(etf_cfg.get("measurement", {}).get("dca_buy_time", "09:00")),
                    now.isoformat(),
                ),
            )


