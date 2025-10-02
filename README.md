# 📊 VOO Dip-Buying Bot (Proof of Concept)

This is a Proof of Concept trading bot that automatically buys ETF dips (VOO, QQQ, SCHD, etc.) on Robinhood. It is designed to test systematic dip-buying rules against a Dollar-Cost Averaging (DCA) baseline.

---

## ⚠️ Disclaimer
- This project is for educational purposes only.
- Use `DRY_RUN=true` to simulate trades without sending live orders.
- Trading involves risk — you can lose money.
- `robin_stocks` is an unofficial API and may break at any time. Use at your own risk.

---

## 🚀 Features
- 3 regimes of dip-buying:
  - Crash: big buy if ETF drops ≥10% intraday.
  - Post-crash drip: small daily buys for N days after a crash.
  - Normal dips: opportunistic buys on 2–3% daily drops or 5% from peak.
- Guardrails: weekly/monthly caps, cash reserve, min/max trade, stale data check.
- Idempotency: never double-buys (each decision has a unique key).
- SQLite DB: records every trade attempt (`placed` or `skipped`) for full audit.
- Weekly measurement: compares Bot vs DCA (portfolio value, average buy price, drawdowns, regime breakdown).
- Backtesting: run historical data through the same rules (e.g., 2008, 2020).

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
DRY_RUN=true   # true = simulate orders; false = send live orders
```

### 2. Config (`config.yaml`)
Example for $500 total cash, scaled budgets:

```yaml
guardrails:
  data_stale_max: "3m"
  order_limit_band_bps: 20
  min_trade: 10
  max_trade: 50
  aggregate_limits:
    weekly_total_cap: 50
    monthly_total_cap: 200

etfs:
  VOO:
    enabled: true
    budgets:
      weekly_cap: 50
      monthly_cap: 200
      cash_reserve_floor: 0.20
    strategy:
      crash:
        panic_threshold: 0.10
        crash_deploy_pct: 0.40
        post_crash_days: 5
        post_crash_total_cap: 0.30
      normal:
        normal_one_day: 0.03
        cumulative: 0.05
        same_day_min: 0.01
    measurement:
      dca_weekly_cap: 50
      dca_buy_day: "MON"
      dca_buy_time: "09:00"
```

---

## 🗄️ Database Design

Tables: `decisions`, `events`, `metrics_weekly` as defined in the codebase.

---

## ⚡ Running the Bot

Modes
- `--mode rth` → every minute during market hours (crash detection)
- `--mode drip` → once per trading day (post-crash drip)
- `--mode eod` → near market close (normal dip)
- `--mode measure` → weekly measurement
- `--mode backtest` → backtest stub
