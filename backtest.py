import logging
import sqlite3
import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
from pathlib import Path
import json

from utils.config_loader import load_config
from rules import RuleDecision, evaluate_crash, evaluate_postcrash_drip, evaluate_normal

logger = logging.getLogger(__name__)


@dataclass
class BacktestPosition:
    """Represents a position in the backtest portfolio"""
    symbol: str
    shares: float = 0.0
    total_cost: float = 0.0
    buy_count: int = 0
    
    @property
    def avg_cost_per_share(self) -> float:
        return self.total_cost / self.shares if self.shares > 0 else 0.0
    
    def add_purchase(self, shares: float, price: float) -> None:
        """Add a purchase to this position"""
        cost = shares * price
        self.total_cost += cost
        self.shares += shares
        self.buy_count += 1


@dataclass
class BacktestPortfolio:
    """Tracks portfolio state during backtesting"""
    cash: float = 10000.0  # Starting cash
    positions: Dict[str, BacktestPosition] = field(default_factory=dict)
    transactions: List[Dict] = field(default_factory=list)
    
    def get_position(self, symbol: str) -> BacktestPosition:
        """Get or create position for symbol"""
        if symbol not in self.positions:
            self.positions[symbol] = BacktestPosition(symbol)
        return self.positions[symbol]
    
    def buy(self, symbol: str, dollars: float, price: float, date: datetime, rule: str, reason: str = "") -> bool:
        """Execute a buy order"""
        if dollars > self.cash:
            logger.warning(f"Insufficient cash: ${dollars:.2f} requested, ${self.cash:.2f} available")
            return False
        
        shares = dollars / price
        position = self.get_position(symbol)
        position.add_purchase(shares, price)
        self.cash -= dollars
        
        # Record transaction
        self.transactions.append({
            'date': date,
            'symbol': symbol,
            'action': 'buy',
            'shares': shares,
            'price': price,
            'dollars': dollars,
            'rule': rule,
            'reason': reason,
            'cash_after': self.cash
        })
        
        logger.debug(f"{date.date()}: Bought ${dollars:.2f} of {symbol} at ${price:.2f} ({shares:.4f} shares) - Rule: {rule}")
        return True
    
    def get_portfolio_value(self, prices: Dict[str, float]) -> float:
        """Calculate total portfolio value"""
        total_value = self.cash
        for symbol, position in self.positions.items():
            if symbol in prices and position.shares > 0:
                total_value += position.shares * prices[symbol]
        return total_value
    
    def get_total_invested(self) -> float:
        """Get total amount invested (excluding cash)"""
        return sum(pos.total_cost for pos in self.positions.values())


@dataclass
class BacktestMetrics:
    """Performance metrics for backtesting"""
    start_date: datetime
    end_date: datetime
    total_return: float = 0.0
    annualized_return: float = 0.0
    volatility: float = 0.0
    sharpe_ratio: float = 0.0
    max_drawdown: float = 0.0
    total_invested: float = 0.0
    final_value: float = 0.0
    buy_count: int = 0
    avg_buy_price: float = 0.0
    win_rate: float = 0.0
    
    def to_dict(self) -> Dict:
        return {
            'start_date': self.start_date.isoformat(),
            'end_date': self.end_date.isoformat(),
            'total_return': self.total_return,
            'annualized_return': self.annualized_return,
            'volatility': self.volatility,
            'sharpe_ratio': self.sharpe_ratio,
            'max_drawdown': self.max_drawdown,
            'total_invested': self.total_invested,
            'final_value': self.final_value,
            'buy_count': self.buy_count,
            'avg_buy_price': self.avg_buy_price,
            'win_rate': self.win_rate
        }


class HistoricalDataLoader:
    """Loads and caches historical price data for backtesting"""
    
    def __init__(self, cache_dir: str = "data/backtest_cache"):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._data_cache = {}
    
    def get_data(self, symbol: str, start_date: datetime, end_date: datetime, 
                 force_refresh: bool = False) -> pd.DataFrame:
        """Get historical data for symbol, using cache when possible"""
        cache_key = f"{symbol}_{start_date.date()}_{end_date.date()}"
        cache_file = self.cache_dir / f"{cache_key}.csv"
        
        # Check memory cache first
        if not force_refresh and cache_key in self._data_cache:
            return self._data_cache[cache_key].copy()
        
        # Check file cache
        if not force_refresh and cache_file.exists():
            try:
                df = pd.read_csv(cache_file)
                self._data_cache[cache_key] = df
                logger.debug(f"Loaded {symbol} data from cache: {len(df)} rows")
                return df.copy()
            except Exception as e:
                logger.warning(f"Failed to load cache file {cache_file}: {e}")
        
        # Fetch from Yahoo Finance
        logger.info(f"Fetching {symbol} data from {start_date.date()} to {end_date.date()}")
        try:
            ticker = yf.Ticker(symbol)
            df = ticker.history(
                start=start_date.date(),
                end=end_date.date(),
                interval="1d",
                auto_adjust=True,
                prepost=False
            )
            
            if df.empty:
                raise ValueError(f"No data returned for {symbol}")
            
            # Reset index to make Date a column
            df = df.reset_index()
            df['Date'] = pd.to_datetime(df['Date'])
            
            # Cache the data
            df.to_csv(cache_file)
            self._data_cache[cache_key] = df
            
            logger.info(f"Fetched {len(df)} rows for {symbol}")
            return df.copy()
            
        except Exception as e:
            logger.error(f"Failed to fetch data for {symbol}: {e}")
            raise
    
    def get_price_on_date(self, symbol: str, date: datetime, 
                         start_date: datetime, end_date: datetime) -> Optional[float]:
        """Get closing price for symbol on specific date"""
        try:
            df = self.get_data(symbol, start_date, end_date)
            date_only = date.date()
            
            # Find exact match first
            exact_match = df[df['Date'].dt.date == date_only]
            if not exact_match.empty:
                return float(exact_match.iloc[0]['Close'])
            
            # Find closest previous trading day
            before_date = df[df['Date'].dt.date <= date_only]
            if not before_date.empty:
                return float(before_date.iloc[-1]['Close'])
            
            logger.warning(f"No price data found for {symbol} on or before {date_only}")
            return None
            
        except Exception as e:
            logger.error(f"Error getting price for {symbol} on {date}: {e}")
            return None


class BacktestEngine:
    """Main backtesting engine"""
    
    def __init__(self, config: Dict, data_loader: HistoricalDataLoader):
        self.config = config
        self.data_loader = data_loader
        self.portfolio = BacktestPortfolio()
        self.crash_events = {}  # symbol -> crash_date mapping
        
    def simulate_data_bundle(self, symbol: str, current_date: datetime, 
                           start_date: datetime, end_date: datetime) -> Dict:
        """Simulate the data bundle that would be available on a given date"""
        try:
            # Get data up to current date (but not including future)
            df = self.data_loader.get_data(symbol, start_date, current_date + timedelta(days=1))
            
            # Filter to only include data up to current date
            df = df[df['Date'].dt.date <= current_date.date()]
            
            if df.empty:
                return {}
            
            # Get recent data (last week for moving averages, etc.)
            recent_df = df.tail(7)  # Last 7 trading days
            
            closes = recent_df['Close'].tolist()
            highs = recent_df['High'].tolist()
            latest_price = float(df.iloc[-1]['Close'])
            
            return {
                'closes': closes,
                'highs': highs,
                'latest_price': latest_price,
                'current_date': current_date
            }
            
        except Exception as e:
            logger.error(f"Error creating data bundle for {symbol} on {current_date}: {e}")
            return {}
    
    def evaluate_rules(self, symbol: str, config: Dict, data: Dict, mode: str) -> Optional[RuleDecision]:
        """Evaluate trading rules using historical data"""
        if not data:
            return None
        
        # Check for crash
        decision = evaluate_crash(symbol, config, data)
        if decision:
            # Record crash event
            current_date = data.get('current_date')
            if current_date:
                self.crash_events[symbol] = current_date.strftime("%Y%m%d")
            return decision
        
        # Check for post-crash drip
        if mode == "post_crash_drip":
            # Simulate active crash event for post-crash evaluation
            if symbol in self.crash_events:
                # Temporarily set the crash event for evaluation
                original_get_event = None
                try:
                    import state
                    original_get_event = state.get_event
                    state.get_event = lambda s: self.crash_events.get(s)
                    decision = evaluate_postcrash_drip(symbol, config, data)
                    if decision:
                        return decision
                finally:
                    if original_get_event:
                        state.get_event = original_get_event
        
        # Check for normal dip buying
        if mode == "eod":
            decision = evaluate_normal(symbol, config, data)
            if decision:
                return decision
        
        return None
    
    def run_backtest(self, symbols: List[str], start_date: datetime, 
                    end_date: datetime, initial_cash: float = 10000.0) -> Dict[str, Any]:
        """Run backtest simulation"""
        logger.info(f"Starting backtest from {start_date.date()} to {end_date.date()}")
        
        self.portfolio.cash = initial_cash
        results = {}
        
        # Get trading days
        trading_days = pd.bdate_range(start=start_date, end=end_date, freq='B')
        
        for current_date in trading_days:
            current_date = current_date.to_pydatetime().replace(tzinfo=timezone.utc)
            
            for symbol in symbols:
                if symbol not in self.config.get('etfs', {}):
                    continue
                
                etf_config = self.config['etfs'][symbol]
                if not etf_config.get('enabled', True):
                    continue
                
                strategy_config = etf_config.get('strategy', {})
                
                # Create data bundle for current date
                data = self.simulate_data_bundle(symbol, current_date, start_date, end_date)
                if not data:
                    continue
                
                # Simulate different trading modes throughout the day
                modes_to_try = ["post_crash_drip", "eod"]  # Simulate both modes
                
                for mode in modes_to_try:
                    decision = self.evaluate_rules(symbol, strategy_config, data, mode)
                    if not decision:
                        continue
                    
                    # Apply budget constraints
                    dollars = self.apply_budget_constraints(
                        symbol, decision.dollars, etf_config, current_date
                    )
                    
                    if dollars < float(self.config.get('guardrails', {}).get('min_trade', 10)):
                        continue
                    
                    # Execute trade
                    price = data['latest_price']
                    success = self.portfolio.buy(
                        symbol=symbol,
                        dollars=dollars,
                        price=price,
                        date=current_date,
                        rule=decision.rule,
                        reason=decision.reason
                    )
                    
                    if success:
                        break  # Only one trade per symbol per day
        
        # Calculate final metrics
        final_prices = {}
        for symbol in symbols:
            price = self.data_loader.get_price_on_date(symbol, end_date, start_date, end_date)
            if price:
                final_prices[symbol] = price
        
        final_value = self.portfolio.get_portfolio_value(final_prices)
        
        # Calculate metrics for each symbol
        for symbol in symbols:
            if symbol in self.portfolio.positions:
                position = self.portfolio.positions[symbol]
                symbol_transactions = [t for t in self.portfolio.transactions if t['symbol'] == symbol]
                
                if symbol_transactions and symbol in final_prices:
                    metrics = self.calculate_metrics(
                        symbol, position, symbol_transactions, final_prices[symbol],
                        start_date, end_date
                    )
                    results[symbol] = metrics
        
        # Overall portfolio metrics
        total_invested = self.portfolio.get_total_invested()
        total_return = (final_value - initial_cash) / initial_cash if initial_cash > 0 else 0
        
        results['portfolio'] = {
            'initial_cash': initial_cash,
            'final_value': final_value,
            'total_invested': total_invested,
            'cash_remaining': self.portfolio.cash,
            'total_return': total_return,
            'transactions': self.portfolio.transactions
        }
        
        logger.info(f"Backtest completed. Final value: ${final_value:.2f}, Total return: {total_return:.2%}")
        return results
    
    def apply_budget_constraints(self, symbol: str, requested_dollars: float, 
                               etf_config: Dict, current_date: datetime) -> float:
        """Apply budget constraints similar to the live trading system"""
        budgets = etf_config.get('budgets', {})
        guardrails = self.config.get('guardrails', {})
        
        # Get spending limits
        min_trade = float(guardrails.get('min_trade', 10))
        max_trade = float(guardrails.get('max_trade', float('inf')))
        
        # For backtesting, we'll use simplified budget constraints
        # In a real implementation, you'd track weekly/monthly spending
        dollars = min(requested_dollars, max_trade)
        dollars = max(0, min(dollars, self.portfolio.cash))
        
        return dollars if dollars >= min_trade else 0
    
    def calculate_metrics(self, symbol: str, position: BacktestPosition, 
                         transactions: List[Dict], final_price: float,
                         start_date: datetime, end_date: datetime) -> BacktestMetrics:
        """Calculate performance metrics for a symbol"""
        if not transactions:
            return BacktestMetrics(start_date=start_date, end_date=end_date)
        
        # Calculate returns
        final_value = position.shares * final_price
        total_return = (final_value - position.total_cost) / position.total_cost if position.total_cost > 0 else 0
        
        # Calculate time-weighted metrics
        days = (end_date - start_date).days
        years = days / 365.25
        annualized_return = (1 + total_return) ** (1/years) - 1 if years > 0 else 0
        
        # Calculate other metrics (simplified for now)
        metrics = BacktestMetrics(
            start_date=start_date,
            end_date=end_date,
            total_return=total_return,
            annualized_return=annualized_return,
            total_invested=position.total_cost,
            final_value=final_value,
            buy_count=position.buy_count,
            avg_buy_price=position.avg_cost_per_share
        )
        
        return metrics


def run_dca_comparison(symbols: List[str], start_date: datetime, end_date: datetime,
                      weekly_amount: float, data_loader: HistoricalDataLoader) -> Dict[str, Any]:
    """Run a simple DCA (Dollar Cost Averaging) comparison"""
    logger.info(f"Running DCA comparison with ${weekly_amount}/week")
    
    results = {}
    trading_weeks = pd.date_range(start=start_date, end=end_date, freq='W-MON')
    
    for symbol in symbols:
        total_invested = 0
        total_shares = 0
        transactions = []
        
        for week_start in trading_weeks:
            week_start = week_start.to_pydatetime().replace(tzinfo=timezone.utc)
            price = data_loader.get_price_on_date(symbol, week_start, start_date, end_date)
            
            if price and price > 0:
                shares = weekly_amount / price
                total_invested += weekly_amount
                total_shares += shares
                
                transactions.append({
                    'date': week_start,
                    'symbol': symbol,
                    'shares': shares,
                    'price': price,
                    'dollars': weekly_amount
                })
        
        # Calculate final value
        final_price = data_loader.get_price_on_date(symbol, end_date, start_date, end_date)
        if final_price and total_shares > 0:
            final_value = total_shares * final_price
            total_return = (final_value - total_invested) / total_invested if total_invested > 0 else 0
            
            results[symbol] = {
                'total_invested': total_invested,
                'total_shares': total_shares,
                'avg_price': total_invested / total_shares if total_shares > 0 else 0,
                'final_value': final_value,
                'final_price': final_price,
                'total_return': total_return,
                'buy_count': len(transactions),
                'transactions': transactions
            }
    
    return results


def save_backtest_results(results: Dict, filename: str = None) -> str:
    """Save backtest results to JSON file"""
    if not filename:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"data/backtest_results_{timestamp}.json"
    
    # Convert datetime objects to strings for JSON serialization
    def serialize_datetime(obj):
        if isinstance(obj, datetime):
            return obj.isoformat()
        elif isinstance(obj, BacktestMetrics):
            return obj.to_dict()
        raise TypeError(f"Object of type {type(obj)} is not JSON serializable")
    
    Path(filename).parent.mkdir(parents=True, exist_ok=True)
    
    with open(filename, 'w') as f:
        json.dump(results, f, indent=2, default=serialize_datetime)
    
    logger.info(f"Backtest results saved to {filename}")
    return filename


def run_backtest() -> None:
    """Main backtest entry point"""
    config = load_config()
    if not config:
        logger.error("Failed to load configuration")
        return
    
    etfs = config.get("etfs", {})
    if not etfs:
        logger.error("No ETFs configured for backtesting")
        return
    
    symbols = [symbol for symbol, cfg in etfs.items() if cfg.get("enabled", True)]
    if not symbols:
        logger.error("No enabled ETFs found")
        return
    
    logger.info(f"Running backtest for {len(symbols)} ETFs: {', '.join(symbols)}")
    
    # Set backtest parameters
    end_date = datetime.now(timezone.utc)
    start_date = end_date - timedelta(days=365)  # 1 year backtest
    initial_cash = 10000.0
    
    # Initialize components
    data_loader = HistoricalDataLoader()
    engine = BacktestEngine(config, data_loader)
    
    try:
        # Run strategy backtest
        logger.info("Running strategy backtest...")
        strategy_results = engine.run_backtest(symbols, start_date, end_date, initial_cash)
        
        # Run DCA comparison
        logger.info("Running DCA comparison...")
        weekly_dca_amount = 50.0  # Default weekly DCA amount
        dca_results = run_dca_comparison(symbols, start_date, end_date, weekly_dca_amount, data_loader)
        
        # Combine results
        final_results = {
            'backtest_params': {
                'start_date': start_date.isoformat(),
                'end_date': end_date.isoformat(),
                'initial_cash': initial_cash,
                'symbols': symbols,
                'weekly_dca_amount': weekly_dca_amount
            },
            'strategy_results': strategy_results,
            'dca_results': dca_results,
            'config_used': config
        }
        
        # Save results
        results_file = save_backtest_results(final_results)
        
        # Print summary
        print("\n" + "="*60)
        print("BACKTEST SUMMARY")
        print("="*60)
        
        if 'portfolio' in strategy_results:
            portfolio = strategy_results['portfolio']
            print(f"Strategy Performance:")
            print(f"  Initial Cash: ${portfolio['initial_cash']:,.2f}")
            print(f"  Final Value:  ${portfolio['final_value']:,.2f}")
            print(f"  Total Return: {portfolio['total_return']:.2%}")
            print(f"  Total Trades: {len(portfolio['transactions'])}")
        
        print(f"\nDCA Comparison:")
        for symbol, dca_data in dca_results.items():
            print(f"  {symbol}:")
            print(f"    Total Invested: ${dca_data['total_invested']:,.2f}")
            print(f"    Final Value:    ${dca_data['final_value']:,.2f}")
            print(f"    Total Return:   {dca_data['total_return']:.2%}")
            print(f"    Buy Count:      {dca_data['buy_count']}")
        
        print(f"\nResults saved to: {results_file}")
        print("="*60)
        
    except Exception as e:
        logger.exception(f"Backtest failed: {e}")
        raise


if __name__ == "__main__":
    run_backtest()
