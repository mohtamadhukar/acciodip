import logging
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Dict, Optional, Tuple

logger = logging.getLogger(__name__)

DB_PATH = Path("data/state.db")
DB_PATH.parent.mkdir(parents=True, exist_ok=True)


@contextmanager
def get_conn():
    conn = sqlite3.connect(DB_PATH)
    try:
        yield conn
    finally:
        conn.commit()
        conn.close()


def init_db() -> None:
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS decisions (
              idempotency_key   TEXT PRIMARY KEY,
              ts                TEXT NOT NULL,
              rule              TEXT NOT NULL CHECK (rule IN ('crash','postcrash_drip','normal')),
              symbol            TEXT NOT NULL,
              dollars           REAL NOT NULL,
              status            TEXT NOT NULL CHECK (status IN ('placed','skipped')),
              reason            TEXT,
              reason_code       TEXT,
              broker_order_id   TEXT,
              filled_qty        REAL,
              filled_avg_price  REAL
            );
            """
        )

        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS events (
              symbol             TEXT PRIMARY KEY,
              active_crash_date  TEXT
            );
            """
        )

        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS metrics_weekly (
              week_ending              TEXT NOT NULL,
              symbol                   TEXT NOT NULL,
              bot_portfolio_value      REAL NOT NULL,
              dca_portfolio_value      REAL NOT NULL,
              bot_total_invested       REAL NOT NULL,
              dca_total_invested       REAL NOT NULL,
              bot_avg_buy_price        REAL,
              dca_avg_buy_price        REAL,
              bot_buy_count_to_date    INTEGER NOT NULL,
              dca_buy_count_to_date    INTEGER NOT NULL,
              bot_max_drawdown_to_date REAL,
              regime_stats_json        TEXT,
              dca_weekly_cap           REAL NOT NULL,
              dca_buy_day              TEXT NOT NULL,
              dca_buy_time             TEXT NOT NULL,
              computed_at              TEXT NOT NULL,
              PRIMARY KEY (week_ending, symbol)
            );
            """
        )


def upsert_event(symbol: str, active_crash_date: Optional[str]) -> None:
    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO events(symbol, active_crash_date)
            VALUES(?, ?)
            ON CONFLICT(symbol) DO UPDATE SET active_crash_date=excluded.active_crash_date
            """,
            (symbol, active_crash_date),
        )


def get_event(symbol: str) -> Optional[str]:
    with get_conn() as conn:
        cur = conn.execute("SELECT active_crash_date FROM events WHERE symbol=?", (symbol,))
        row = cur.fetchone()
        return row[0] if row else None


def has_decision(idempotency_key: str) -> bool:
    with get_conn() as conn:
        cur = conn.execute("SELECT 1 FROM decisions WHERE idempotency_key=?", (idempotency_key,))
        return cur.fetchone() is not None


def sum_spent(symbol: Optional[str], start_iso: Optional[str], end_iso: Optional[str]) -> float:
    sql = "SELECT COALESCE(SUM(dollars), 0) FROM decisions WHERE status='placed'"
    params: Tuple = tuple()
    if symbol:
        sql += " AND symbol=?"
        params += (symbol,)
    if start_iso:
        sql += " AND ts>=?"
        params += (start_iso,)
    if end_iso:
        sql += " AND ts<?"
        params += (end_iso,)
    with get_conn() as conn:
        cur = conn.execute(sql, params)
        row = cur.fetchone()
        return float(row[0] or 0)


def insert_decision(row: Dict) -> None:
    with get_conn() as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO decisions(
                idempotency_key, ts, rule, symbol, dollars, status, reason, reason_code, broker_order_id, filled_qty, filled_avg_price
            ) VALUES(?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                row["idempotency_key"],
                row["ts"],
                row["rule"],
                row["symbol"],
                row["dollars"],
                row["status"],
                row.get("reason"),
                row.get("reason_code"),
                row.get("broker_order_id"),
                row.get("filled_qty"),
                row.get("filled_avg_price"),
            ),
        )


