## acciodip
An intelligent dip‑buying bot that helps automate ETF investing during market pullbacks — balancing discipline, safety, and simplicity.

### What this is
- **Goal**: Systematically buy broad‑market ETFs only when there’s a meaningful pullback.
- **Approach**: Detect dips from recent highs, ensure the day’s drop is significant, and enforce weekly budgets and cash reserves before placing any orders.
- **Current state**: Detection and plumbing are implemented. The actual buy paths are present but commented out for safety by default.

### How it works (high‑level)
At a regular cadence, the bot evaluates each configured ETF independently and may decide to place a buy. The logic emphasizes disciplined entry, budget control, and safety interlocks.

1) Inputs it evaluates for each ETF
- **Recent dip**: How far the current price is below the last week’s high. This gauges whether the market has actually pulled back.
- **Today’s change**: How much the price moved since yesterday’s close. This avoids buying on flat days and focuses on material drawdowns.
- **Available budget**: How much weekly allocation remains for the ETF and how much free cash is available beyond a configured reserve.
- **Recent activity**: Recent orders to infer whether we are in a post‑crash recovery window.

2) Eligibility checks before buying
- **Meaningful pullback filter**: Only consider buys when the dip exceeds a configured threshold (e.g., ≥ 5–6%).
- **Same‑day pressure filter**: Require today’s drop to exceed a minimum threshold (e.g., ≥ 2%), ensuring momentum is actually down.
- **Budget guardrails**: Do not exceed the ETF’s weekly limit and never consume the configured cash reserve.
- **Frequency controls**: Cooldown hours and max buys per day (planned) prevent clustering of multiple buys too tightly in time.

3) Regime selection
- **Crash day**: If today’s drop surpasses a “panic” threshold (e.g., ≥ 10%), immediately deploy a defined percentage of the weekly limit. Rationale: crashes are rare; acting decisively captures unusually favorable prices.
- **Post‑crash recovery**: For several days after a crash, place small, fixed‑size buys daily. Rationale: spreads entry across ongoing volatility while maintaining exposure.
- **Normal dip**: If neither crash nor post‑crash conditions apply but a meaningful dip is present along with a sufficient same‑day drop, deploy remaining budget subject to guardrails.

4) Sizing and risk controls
- **Weekly budget cap**: Per‑ETF weekly allocations limit total spend regardless of how many signals occur.
- **Cash reserve**: Maintain a minimum cash balance; if spending would breach it, the order is skipped or sized down.
- **Price‑based quantity**: The buy amount translates to a share quantity using the latest price; fractional sizing keeps sizing precise.

5) Observability and safety
- **Explicit logs**: Every decision point (eligibility, regime selection, sizing) is logged so you can audit behavior before enabling live trades.
- **Fail‑closed defaults**: If inputs are missing/invalid, or guardrails fail, the bot does not buy.
- **Manual arming**: Execution branches that place live orders are present but disabled by default; you must explicitly enable them when ready.

Note: Buy execution branches are intentionally disabled out‑of‑the‑box to prevent accidental live trading. See “Enable live trading” below.

#### Decision flow (visual)

```mermaid
flowchart TD
    A[Start / Scheduled run] --> B[Load config and state]
    B --> C[Fetch prices, historicals, cash, recent orders]
    C --> D{Data valid?}
    D -- No --> Z[Log and skip]
    D -- Yes --> E[Compute dip vs 7-day high and today's % change]

    E --> F{Today's drop ≥ panic threshold?}
    F -- Yes --> G[Crash regime]
    G --> G1[Size = crash_day_buy_percent × weekly_limit]
    G1 --> H{Guardrails ok? (weekly_limit, min_cash_reserve)}
    H -- No --> Z
    H -- Yes --> Y[Execute buy (disabled by default)]

    F -- No --> I{In post-crash window?}
    I -- Yes --> J[Post-crash regime]
    J --> J1[Size = post_crash_buy_amount]
    J1 --> H

    I -- No --> K{Dip ≥ threshold AND today's drop ≥ threshold?}
    K -- No --> Z
    K -- Yes --> L[Normal dip regime]
    L --> L1[Size = min(weekly remaining, cash - reserve)]
    L1 --> H

    Y --> X[Log decision and outcome]
    Z --> X
```

### Key files
- `main.py`: Entrypoint and logging configuration.
- `config.yaml`: Strategy configuration for general rules and per‑ETF thresholds/limits.
- `services/dip_buyer.py`: Orchestrates dip detection and (optionally) trading decisions.
- `utils/dip_checks.py`: Computes dip from last week’s high and today’s change.
- `utils/robinhood_api.py`: Light wrapper around `robin-stocks` for auth, quotes, orders, and history.

### Configuration
All strategy knobs live in `config.yaml`.

General settings:
- `general.min_cash_reserve`: Dollars to always keep uninvested. Orders are capped so cash never drops below this.
- `general.cooldown_hours`: Intended to enforce time spacing between buys. (Not yet enforced in code.)
- `general.max_buys_per_day`: Intended cap on buys per ETF per day. (Not yet enforced in code.)

Per‑ETF settings (example keys in the repo for `VOO` and `QQQ`):
- `weekly_limit`: Max dollars to spend per week for that ETF.
- `dip_threshold_percent`: Minimum dip from the last 7‑day high to consider buying.
- `today_drop_threshold`: Minimum same‑day drop to consider buying.
- `panic_drop_threshold`: If the day’s drop exceeds this, treat as a crash day.
- `crash_day_buy_percent`: Percent of weekly limit to deploy immediately on a crash day.
- `post_crash_buy_amount`: Daily buy amount during post‑crash recovery.
- `post_crash_days`: Number of days to continue staged buys after a crash.

### Dip detection
Implemented in `utils/dip_checks.py` using Robinhood historicals:
- Pulls a week of daily candles.
- Computes dip percent = (weekly_high − today_close) / weekly_high.
- Computes today’s change = (today_close − yesterday_close) / yesterday_close.
- Returns `(dip_percent, today_change_percent)`.

### Spending and sizing
The function `available_to_invest(cash, weekly_spend, etf_settings)` ensures:
- Never spend beyond `weekly_limit` minus what you already spent this week on that ETF.
- Never reduce cash below `general.min_cash_reserve`.

Order quantity is computed as `dollars / latest_price` with 4‑decimal rounding before placing a market buy.

### Robinhood integration
`utils/robinhood_api.py` uses `robin-stocks` to:
- Log in/out of Robinhood.
- Fetch account cash, latest prices, and historical candles.
- Fetch recent orders and classify them to distinguish crash‑day buys vs normal buys.

Important: MFA is supported via TOTP in the helper, but currently commented out for convenience. You should re‑enable TOTP and remove hard‑coded credentials before live trading.

### Running locally
1. Create and activate a virtual environment (recommended).
2. Install dependencies.
3. Populate `config.yaml` with your tickers and thresholds.
4. Configure credentials securely (see next section).
5. Run the bot.

```bash
python -m venv .venv
source .venv/bin/activate  # macOS/Linux
pip install -r requirements.txt
python main.py
```

### Credentials and MFA
By default, `services/dip_buyer.py` contains placeholder credentials in `login_robinhood(...)`. Do not commit your credentials. A safer approach:
1. Store credentials as environment variables and pass them into `login_robinhood`.
2. Re‑enable the TOTP flow in `utils/robinhood_api.py` and provide your MFA seed via env var.

Example pattern to adopt in your code (you must make the edits):

```python
import os
login_robinhood(
    username=os.environ["RH_USERNAME"],
    password=os.environ["RH_PASSWORD"],
    mfa_key=os.environ.get("RH_MFA_KEY")
)
```

Then set locally (e.g., in your shell or a local `.env` you do not commit):

```bash
export RH_USERNAME="you@example.com"
export RH_PASSWORD="your-password"
export RH_MFA_KEY="base32totpseed"
```

In `utils/robinhood_api.py`, uncomment the TOTP lines and pass `mfa_code=totp` to `r.login(...)`.

### Enable live trading (optional)
The three buy paths are intentionally commented out in `services/dip_buyer.py` to prevent accidental orders:

```python
# if today_change_percent <= -etf_settings['panic_drop_threshold']:
#     handle_crash_buy(...)
# elif is_in_post_crash_mode(...):
#     handle_post_crash_staged_buy(...)
# elif dip_percent >= ... and today_change_percent <= -...:
#     handle_normal_dip_buy(...)
```

Only after you’ve tested read‑only detection and validated logs, you can manually uncomment the relevant blocks to enable live orders.

### Logs
`main.py` logs to both stdout and `bot.log` with timestamps and levels. Use this to validate detection, sizing, and guardrails before enabling trades.

### What’s implemented vs planned
- Implemented: dip detection, sizing with weekly limit and cash reserve, order plumbing, recent orders fetch, basic classification, logging.
- Present but commented: crash/post‑crash/normal buy execution paths.
- Planned/TODO: enforce `cooldown_hours` and `max_buys_per_day` in code; stronger weekly‑spent calculation from order fills; robust error handling and retries.

### Safety and disclaimers
- This is not financial advice. Use at your own risk.
- Test in read‑only mode first. Inspect logs and confirm math.
- Keep credentials out of source control; use environment variables and MFA.

### Requirements
See `requirements.txt`. Core packages: `pyyaml`, `robin-stocks`, `pyotp`.

### License
This project includes third‑party code (`robin_stocks` vendored docs) under their respective licenses. See `LICENSE.txt` where applicable.
