# Backtesting System Documentation

## Overview

The backtesting system allows you to test your dip-buying strategies against historical market data to evaluate their performance before deploying them with real money. The system simulates the exact same trading rules and logic used in live trading.

## Key Features

- **Historical Data Integration**: Fetches and caches historical price data from Yahoo Finance
- **Strategy Simulation**: Simulates crash detection, post-crash drip buying, and normal dip buying
- **Portfolio Tracking**: Tracks positions, cash, and performance metrics over time
- **DCA Comparison**: Compares strategy performance against simple Dollar Cost Averaging
- **Performance Metrics**: Calculates returns, Sharpe ratios, drawdowns, and other key metrics
- **Result Persistence**: Saves detailed results to JSON files for later analysis

## Quick Start

### Basic Backtest

Run a basic backtest using your current configuration:

```bash
python main.py --mode backtest
```

This will:
- Load your current `config.yaml` settings
- Run a 1-year backtest ending today
- Compare against DCA strategy
- Save results to `data/backtest_results_YYYYMMDD_HHMMSS.json`
- Print a summary to the console

### Custom Backtest

For more control, use the example script:

```bash
python backtest_example.py custom
```

This runs a 2-year backtest with $25,000 starting capital and compares against multiple DCA strategies.

## System Components

### 1. HistoricalDataLoader

Handles fetching and caching historical price data:

```python
from backtest import HistoricalDataLoader

loader = HistoricalDataLoader()
data = loader.get_data('VOO', start_date, end_date)
price = loader.get_price_on_date('VOO', specific_date, start_date, end_date)
```

**Features:**
- Automatic caching to `data/backtest_cache/` directory
- Memory and disk caching for performance
- Handles missing trading days gracefully

### 2. BacktestPortfolio

Tracks portfolio state during simulation:

```python
from backtest import BacktestPortfolio

portfolio = BacktestPortfolio(cash=10000.0)
success = portfolio.buy('VOO', 100.0, 450.0, datetime.now(), 'crash', 'Market crash detected')
total_value = portfolio.get_portfolio_value({'VOO': 460.0})
```

**Features:**
- Position tracking with cost basis
- Transaction history
- Cash management
- Portfolio valuation

### 3. BacktestEngine

Main simulation engine:

```python
from backtest import BacktestEngine, HistoricalDataLoader
from utils.config_loader import load_config

config = load_config()
loader = HistoricalDataLoader()
engine = BacktestEngine(config, loader)

results = engine.run_backtest(['VOO'], start_date, end_date, 10000.0)
```

**Features:**
- Simulates trading rules exactly as in live system
- Handles crash events and post-crash drip periods
- Applies budget constraints and guardrails
- Calculates comprehensive performance metrics

## Configuration

The backtesting system uses the same `config.yaml` file as live trading. Key sections:

```yaml
guardrails:
  min_trade: 10                 # Minimum trade size
  max_trade: 50                 # Maximum trade size
  
etfs:
  VOO:
    enabled: true
    budgets:
      weekly_cap: 50            # Weekly spending limit
      monthly_cap: 200          # Monthly spending limit
    strategy:
      crash:
        panic_threshold: 0.10   # 10% drop = crash
        crash_deploy_pct: 0.40  # Deploy 40% of weekly budget
        post_crash_days: 5      # Drip for 5 days after crash
        post_crash_total_cap: 0.30  # 30% of weekly budget for drips
      normal:
        normal_one_day: 0.03    # 3% daily drop triggers buy
        cumulative: 0.05        # 5% from peak also triggers buy
        same_day_min: 0.01      # Must drop at least 1% same day
```

## Understanding Results

### Strategy Results

```json
{
  "portfolio": {
    "initial_cash": 10000.0,
    "final_value": 11250.0,
    "total_invested": 2400.0,
    "cash_remaining": 7600.0,
    "total_return": 0.125,
    "transactions": [...]
  }
}
```

- `final_value`: Total portfolio value at end (cash + positions)
- `total_invested`: Amount deployed into positions
- `cash_remaining`: Uninvested cash
- `total_return`: Overall portfolio return
- `transactions`: Detailed trade history

### DCA Comparison

```json
{
  "VOO": {
    "total_invested": 2600.0,
    "final_value": 2890.0,
    "total_return": 0.112,
    "avg_price": 445.50,
    "buy_count": 52
  }
}
```

- `total_invested`: Total amount invested via DCA
- `final_value`: Value of DCA position at end
- `total_return`: DCA strategy return
- `avg_price`: Average purchase price
- `buy_count`: Number of DCA purchases

### Performance Metrics

For each symbol, detailed metrics are calculated:

- **Total Return**: Overall gain/loss percentage
- **Annualized Return**: Return adjusted for time period
- **Buy Count**: Number of purchases made
- **Average Buy Price**: Average price paid per share

## Advanced Usage

### Parameter Sensitivity Analysis

Test how different parameters affect performance:

```bash
python backtest_example.py sensitivity
```

This tests different crash thresholds (5%, 8%, 10%, 12%, 15%) and shows how performance varies.

### Analyzing Saved Results

Analyze previously saved backtest results:

```bash
python backtest_example.py analyze data/backtest_results_20241002_143022.json
```

### Custom Time Periods

```python
from datetime import datetime, timedelta, timezone
from backtest import BacktestEngine, HistoricalDataLoader
from utils.config_loader import load_config

# Test during 2020 market crash
start_date = datetime(2020, 1, 1, tzinfo=timezone.utc)
end_date = datetime(2020, 12, 31, tzinfo=timezone.utc)

config = load_config()
loader = HistoricalDataLoader()
engine = BacktestEngine(config, loader)

results = engine.run_backtest(['VOO'], start_date, end_date, 10000.0)
```

### Multiple Symbols

Test across multiple ETFs:

```python
symbols = ['VOO', 'VTI', 'VXUS', 'BND']
results = engine.run_backtest(symbols, start_date, end_date, 50000.0)
```

## Data Requirements

### Yahoo Finance Data

The system uses Yahoo Finance for historical data:
- Daily OHLCV data
- Automatically handles stock splits and dividends
- Caches data locally for performance

### Cache Management

Historical data is cached in `data/backtest_cache/`:
- Files are named: `{SYMBOL}_{START_DATE}_{END_DATE}.parquet`
- Delete cache files to force refresh
- Cache includes both memory and disk layers

## Performance Considerations

### Speed Optimization

- Data is cached aggressively to avoid repeated API calls
- Use shorter time periods for faster iteration
- Consider running sensitivity analysis on smaller date ranges first

### Memory Usage

- Large backtests (multiple years, many symbols) can use significant memory
- Clear cache periodically if running many backtests
- Consider processing symbols individually for very large analyses

## Troubleshooting

### Common Issues

1. **No data returned for symbol**
   - Check symbol spelling
   - Ensure symbol existed during backtest period
   - Try a different date range

2. **Cache errors**
   - Delete cache files in `data/backtest_cache/`
   - Check disk space
   - Ensure write permissions

3. **No trades executed**
   - Check if crash/dip thresholds are too strict
   - Verify budget constraints aren't too restrictive
   - Review guardrails settings

### Debug Mode

Enable debug logging for detailed information:

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

## Interpreting Results

### Strategy Effectiveness

Good indicators of strategy effectiveness:
- **Outperforms DCA**: Strategy return > DCA return
- **Reasonable Trade Count**: Not too many (overtrading) or too few (underutilized)
- **Consistent Performance**: Works across different time periods

### Risk Assessment

Consider these risk factors:
- **Cash Utilization**: High cash remaining may indicate missed opportunities
- **Concentration Risk**: Too many trades in short periods
- **Market Timing**: Performance heavily dependent on specific market events

### Optimization Guidelines

1. **Start Conservative**: Begin with higher thresholds, lower deploy percentages
2. **Test Multiple Periods**: Include bull markets, bear markets, and sideways periods
3. **Compare Alternatives**: Test against buy-and-hold and regular DCA
4. **Consider Transaction Costs**: Real trading includes fees and spreads

## Example Workflows

### Strategy Development

1. Start with paper trading configuration
2. Run 1-year backtest to get baseline
3. Adjust parameters based on results
4. Run sensitivity analysis on key parameters
5. Test on different time periods
6. Compare against benchmarks
7. Deploy with small amounts initially

### Performance Monitoring

1. Run monthly backtests on recent periods
2. Compare live results to backtest predictions
3. Adjust parameters if significant deviations occur
4. Archive results for long-term analysis

## Files and Directories

```
acciodip/
├── backtest.py              # Main backtesting engine
├── backtest_example.py      # Example usage and analysis
├── BACKTESTING.md          # This documentation
├── data/
│   ├── backtest_cache/     # Cached historical data
│   └── backtest_results_*  # Saved backtest results
└── config.yaml             # Strategy configuration
```

## Next Steps

After running backtests:

1. **Analyze Results**: Look for patterns in trading behavior
2. **Optimize Parameters**: Use sensitivity analysis to find optimal settings
3. **Validate Strategy**: Test on out-of-sample periods
4. **Paper Trade**: Run live system in dry-run mode
5. **Deploy Gradually**: Start with small amounts and scale up

Remember: Past performance does not guarantee future results. Always start with small amounts and monitor performance closely.
