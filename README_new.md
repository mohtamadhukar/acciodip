# 📊 VOO Dip-Buying Bot (Proof of Concept)

This is a **Proof of Concept trading bot** that automatically buys ETF dips (VOO, QQQ, SCHD, etc.) on Robinhood.  
It is designed to test systematic dip-buying rules against a **Dollar-Cost Averaging (DCA) baseline**.

---

## ⚠️ Disclaimer
- This project is **for educational purposes only**.  
- Use **`DRY_RUN=true`** to simulate trades without sending live orders.  
- Trading involves risk — you can lose money.  
- `robin_stocks` is an **unofficial API** and may break at any time. Use at your own risk.

---

## 🚀 Features
- **3 regimes of dip-buying**:
  - **Crash**: big buy if ETF drops ≥10% intraday.
  - **Post-crash drip**: small daily buys for N days after a crash.
  - **Normal dips**: opportunistic buys on 2–3% daily drops or 5% from peak.
- **Guardrails**: weekly/monthly caps, cash reserve, min/max trade, stale data check.
- **Idempotency**: never double-buys (each decision has a unique key).
- **SQLite DB**: records every trade attempt (`placed` or `skipped`) for full audit.
- **Weekly measurement**: compares Bot vs DCA (portfolio value, average buy price, drawdowns, regime breakdown).
- **Backtesting**: run historical data through the same rules (e.g., 2008, 2020).

---

## 📜 Business Rules

The bot uses simple business rules with clear priorities:

### 1. Crash Day
- **Trigger:** intraday drop ≥ 10% vs prior close.  
- **Action:** immediately deploy 40% of weekly budget (scaled to config).  
- **Effect:** set bot into *post-crash mode* for N days.

### 2. Post-Crash Drip
- **Trigger:** days following a crash while in post-crash mode.  
- **Action:** buy small fixed amount daily (up to 30% of weekly cap spread over drip days).  
- **End conditions:** recovery above pre-crash high or days exhausted.

### 3. Normal Dip
- **Trigger:** daily drop ≥ 2–3% or cumulative drop ≥ 5% from peak, plus same-day confirmation drop ≥ 1%.  
- **Action:** buy leftover budget, clamped to min/max trade.  
- **Only allowed when not in post-crash mode.**

### Priorities
- Crash > Post-Crash Drip > Normal Dip. Only one regime can fire per run.

### Guardrails
- Skip if data stale > 3 minutes.
- Weekly/monthly caps enforced.
- Cash reserve floor enforced.
- Min/max trade enforced.
- Aggregate caps across all ETFs enforced if set.

---

## 🗂️ Repo Structure
```
voo-bot/
  main.py                # orchestrator; runs rules by mode
  rules.py               # dip-buying logic (crash, postcrash_drip, normal)
  broker_robinhood.py    # Robinhood login + order helpers
  data_robinhood.py      # market data helpers (prices, closes)
  state.py               # SQLite accessors (decisions, events, metrics)
  measure.py             # weekly measurement job (Bot vs DCA)
  backtest.py            # offline backtest (historical data)
  config.yaml            # per-ETF config + guardrails
  requirements.txt       # Python deps
  logs/                  # log files
  data/state.db          # SQLite DB (auto-created)
  .env                   # secrets (Robinhood login, DRY_RUN flag)
```

---

## ⚙️ Installation
```bash
# Clone repo
git clone <your-repo-url>
cd voo-bot

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

---

## 🔑 Setup

### 1. Environment (`.env`)
```bash
RH_USERNAME=you@example.com
RH_PASSWORD=your-password
RH_MFA_CODE=   # leave blank if using SMS or app MFA flow
DRY_RUN=true   # true = simulate orders; false = send live orders
```

### 2. Config (`config.yaml`)
Example for $500 total cash, scaled budgets:

```yaml
# =========================================
# Global guardrails (apply to all ETFs)
# =========================================
guardrails:
  data_stale_max: "3m"          # skip trades if quote older than this
  order_limit_band_bps: 20      # buy limit up to +0.20% above last price
  min_trade: 10                 # $ minimum per order
  max_trade: 50                 # $ maximum per order
  aggregate_limits:             # caps across all ETFs (optional)
    weekly_total_cap: 50        # $ max spend across all ETFs per week
    monthly_total_cap: 200      # $ max spend across all ETFs per month

# =========================================
# Per-ETF settings
# =========================================
etfs:

  VOO:
    enabled: true
    budgets:
      weekly_cap: 50            # $ max spend per week
      monthly_cap: 200          # $ max spend per month
      cash_reserve_floor: 0.20  # fraction of cash to keep (0.20 = 20%)
    strategy:
      crash:
        panic_threshold: 0.10        # 10% drop in one day = crash
        crash_deploy_pct: 0.40       # 40% of weekly budget on crash day
        post_crash_days: 5           # number of drip days after crash
        post_crash_total_cap: 0.30   # 30% of weekly budget for drips
      normal:
        normal_one_day: 0.03         # 3% daily drop triggers normal dip
        cumulative: 0.05             # 5% from recent peak also qualifies
        same_day_min: 0.01           # must drop at least 1% same day
    measurement:
      dca_weekly_cap: 50             # $ to simulate weekly DCA
      dca_buy_day: "MON"             # DCA buy day (MON..FRI)
      dca_buy_time: "09:00"          # DCA buy time (HH:MM)
```

---

## 🗄️ Database Design

### Tables

#### 1. decisions
Ledger of every decision (placed or skipped). Provides idempotency and audit trail.

```sql
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
```

**When to update:**
- Before placing → insert row with status='placed'.
- If blocked by guardrails → insert row with status='skipped'.
- After placing order → update broker_order_id, filled_qty, filled_avg_price.

** Idempotency key format **:
Crash: YYYYMMDD-crash-<crash_event_id>
Post-crash drip: YYYYMMDD-postcrash_drip-<crash_event_id>
Normal: YYYYMMDD-normal-none

#### 2. events
Tracks whether post-crash mode is active.

```sql
CREATE TABLE IF NOT EXISTS events (
  symbol             TEXT PRIMARY KEY,
  active_crash_date  TEXT
);
```

**When to update:**
- On crash buy → set active_crash_date=today.
- On recovery or drip exhaustion → set active_crash_date=NULL.

#### 3. metrics_weekly
Stores weekly measurement vs DCA.

```sql
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
```

**When to update:**
- Once per week by `measure.py`.
- Snapshot DCA config values used that week.

### Example Rows

**decisions**
| idempotency_key                   | ts                        | rule            | symbol | dollars | status  | reason               | reason_code        | broker_order_id | filled_qty | filled_avg_price |
|-----------------------------------|---------------------------|-----------------|--------|---------|---------|----------------------|-------------------|-----------------|------------|------------------|
| 20251001-crash-20251001           | 2025-10-01T10:35:00-05:00 | crash           | VOO    | 20      | placed  | drop=-11%            |                   | RH12345         | 0.05       | 400.00           |
| 20251002-postcrash_drip-20251001  | 2025-10-02T08:40:00-05:00 | postcrash_drip  | VOO    | 5       | placed  | post-crash day 1     |                   | RH12399         | 0.013      | 384.62           |
| 20251002-normal-none              | 2025-10-02T14:55:00-05:00 | normal          | VOO    | 30      | skipped | post-crash active    | POST_CRASH_ACTIVE |                 |            |                  |

**events**
| symbol | active_crash_date |
|--------|--------------------|
| VOO    | 2025-10-01         |

**metrics_weekly**
| week_ending | symbol | bot_portfolio_value | dca_portfolio_value | bot_total_invested | dca_total_invested | bot_avg_buy_price | dca_avg_buy_price | bot_buy_count_to_date | dca_buy_count_to_date | bot_max_drawdown_to_date | regime_stats_json                                          | dca_weekly_cap | dca_buy_day | dca_buy_time | computed_at |
|-------------|--------|---------------------|---------------------|--------------------|--------------------|-------------------|-------------------|-----------------------|-----------------------|---------------------------|-----------------------------------------------------------|----------------|------------|-------------|-------------|
| 2025-10-03  | VOO    | 10900.00            | 10700.00            | 5300.00            | 5000.00            | 382.10            | 388.00            | 3                     | 2                     | -0.15                      | {"crash":{"count":1,"dollars":20,"avg_entry":380.95},"postcrash_drip":{"count":1,"dollars":5,"avg_entry":384.62},"normal":{"count":0,"dollars":0}} | 50             | MON        | 09:00       | 2025-10-03T17:35:00-05:00 |

---

## ⚡ Running the Bot

### Modes
- `--mode rth` → every minute during market hours (crash detection)  
- `--mode drip` → once per trading day (post-crash drip)  
- `--mode eod` → near market close (normal dip)  
- `--mode finalize` → after close (update anchors, reset crash flags)  
- `--mode weekly_reset` → weekly budget reset  