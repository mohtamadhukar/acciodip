#!/usr/bin/env python3
"""
Example script demonstrating how to use the backtesting system.

This script shows various ways to run backtests and analyze results.
"""

import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path

from backtest import (
    HistoricalDataLoader, 
    BacktestEngine, 
    run_dca_comparison,
    save_backtest_results
)
from utils.config_loader import load_config

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def run_custom_backtest():
    """Run a custom backtest with specific parameters"""
    logger.info("Running custom backtest example...")
    
    # Load configuration
    config = load_config()
    if not config:
        logger.error("Failed to load configuration")
        return
    
    # Set custom parameters
    end_date = datetime.now(timezone.utc)
    start_date = end_date - timedelta(days=730)  # 2 years
    initial_cash = 25000.0  # $25k starting capital
    symbols = ['VOO']  # Focus on VOO for this example
    
    logger.info(f"Backtest period: {start_date.date()} to {end_date.date()}")
    logger.info(f"Initial capital: ${initial_cash:,.2f}")
    logger.info(f"Symbols: {', '.join(symbols)}")
    
    # Initialize components
    data_loader = HistoricalDataLoader()
    engine = BacktestEngine(config, data_loader)
    
    try:
        # Run strategy backtest
        logger.info("Running strategy backtest...")
        strategy_results = engine.run_backtest(symbols, start_date, end_date, initial_cash)
        
        # Run DCA comparison with different amounts
        dca_amounts = [50.0, 100.0, 200.0]  # Weekly DCA amounts to compare
        dca_comparisons = {}
        
        for weekly_amount in dca_amounts:
            logger.info(f"Running DCA comparison with ${weekly_amount}/week...")
            dca_results = run_dca_comparison(symbols, start_date, end_date, weekly_amount, data_loader)
            dca_comparisons[f"dca_{weekly_amount}"] = dca_results
        
        # Combine results
        final_results = {
            'backtest_params': {
                'start_date': start_date.isoformat(),
                'end_date': end_date.isoformat(),
                'initial_cash': initial_cash,
                'symbols': symbols,
                'backtest_type': 'custom_example'
            },
            'strategy_results': strategy_results,
            'dca_comparisons': dca_comparisons,
            'config_used': config
        }
        
        # Save results
        results_file = save_backtest_results(final_results, "data/custom_backtest_example.json")
        
        # Print detailed analysis
        print_detailed_analysis(final_results)
        
        logger.info(f"Custom backtest completed. Results saved to: {results_file}")
        
    except Exception as e:
        logger.exception(f"Custom backtest failed: {e}")
        raise


def print_detailed_analysis(results):
    """Print detailed analysis of backtest results"""
    print("\n" + "="*80)
    print("DETAILED BACKTEST ANALYSIS")
    print("="*80)
    
    params = results['backtest_params']
    strategy = results['strategy_results']
    dca_comparisons = results['dca_comparisons']
    
    print(f"Backtest Period: {params['start_date'][:10]} to {params['end_date'][:10]}")
    print(f"Initial Capital: ${params['initial_cash']:,.2f}")
    print(f"Symbols Tested: {', '.join(params['symbols'])}")
    
    if 'portfolio' in strategy:
        portfolio = strategy['portfolio']
        print(f"\nSTRATEGY PERFORMANCE:")
        print(f"  Final Portfolio Value: ${portfolio['final_value']:,.2f}")
        print(f"  Total Amount Invested: ${portfolio['total_invested']:,.2f}")
        print(f"  Cash Remaining:        ${portfolio['cash_remaining']:,.2f}")
        print(f"  Total Return:          {portfolio['total_return']:.2%}")
        print(f"  Number of Trades:      {len(portfolio['transactions'])}")
        
        if portfolio['transactions']:
            # Analyze trading patterns
            trades_by_rule = {}
            for trade in portfolio['transactions']:
                rule = trade['rule']
                trades_by_rule[rule] = trades_by_rule.get(rule, 0) + 1
            
            print(f"\n  Trading Pattern Analysis:")
            for rule, count in trades_by_rule.items():
                print(f"    {rule.title()} trades: {count}")
            
            # Show first and last few trades
            print(f"\n  First 3 Trades:")
            for i, trade in enumerate(portfolio['transactions'][:3]):
                date = trade['date'][:10] if isinstance(trade['date'], str) else trade['date'].strftime('%Y-%m-%d')
                print(f"    {i+1}. {date}: ${trade['dollars']:.2f} of {trade['symbol']} at ${trade['price']:.2f} ({trade['rule']})")
            
            if len(portfolio['transactions']) > 3:
                print(f"  Last 3 Trades:")
                for i, trade in enumerate(portfolio['transactions'][-3:]):
                    date = trade['date'][:10] if isinstance(trade['date'], str) else trade['date'].strftime('%Y-%m-%d')
                    idx = len(portfolio['transactions']) - 3 + i + 1
                    print(f"    {idx}. {date}: ${trade['dollars']:.2f} of {trade['symbol']} at ${trade['price']:.2f} ({trade['rule']})")
    
    # DCA Comparison Analysis
    print(f"\nDCA COMPARISON ANALYSIS:")
    for dca_name, dca_data in dca_comparisons.items():
        weekly_amount = dca_name.split('_')[1]
        print(f"\n  DCA Strategy (${weekly_amount}/week):")
        
        for symbol, data in dca_data.items():
            print(f"    {symbol}:")
            print(f"      Total Invested:    ${data['total_invested']:,.2f}")
            print(f"      Final Value:       ${data['final_value']:,.2f}")
            print(f"      Total Return:      {data['total_return']:.2%}")
            print(f"      Average Buy Price: ${data['avg_price']:.2f}")
            print(f"      Number of Buys:    {data['buy_count']}")
    
    # Strategy vs DCA Comparison
    if 'portfolio' in strategy and dca_comparisons:
        print(f"\nSTRATEGY vs DCA COMPARISON:")
        strategy_return = strategy['portfolio']['total_return']
        
        for dca_name, dca_data in dca_comparisons.items():
            weekly_amount = dca_name.split('_')[1]
            
            # Calculate weighted average return across all symbols in DCA
            total_invested_dca = sum(data['total_invested'] for data in dca_data.values())
            total_final_dca = sum(data['final_value'] for data in dca_data.values())
            dca_return = (total_final_dca - total_invested_dca) / total_invested_dca if total_invested_dca > 0 else 0
            
            outperformance = strategy_return - dca_return
            print(f"  Strategy vs DCA (${weekly_amount}/week):")
            print(f"    Strategy Return:     {strategy_return:.2%}")
            print(f"    DCA Return:          {dca_return:.2%}")
            print(f"    Outperformance:      {outperformance:+.2%}")
    
    print("="*80)


def analyze_existing_results(results_file: str):
    """Analyze results from a previously saved backtest"""
    import json
    
    logger.info(f"Analyzing existing results from: {results_file}")
    
    try:
        with open(results_file, 'r') as f:
            results = json.load(f)
        
        print_detailed_analysis(results)
        
    except Exception as e:
        logger.error(f"Failed to analyze results file {results_file}: {e}")


def run_parameter_sensitivity_analysis():
    """Run backtests with different parameter settings to test sensitivity"""
    logger.info("Running parameter sensitivity analysis...")
    
    config = load_config()
    if not config:
        logger.error("Failed to load configuration")
        return
    
    # Test different crash thresholds
    crash_thresholds = [0.05, 0.08, 0.10, 0.12, 0.15]  # 5% to 15%
    
    end_date = datetime.now(timezone.utc)
    start_date = end_date - timedelta(days=365)  # 1 year
    initial_cash = 10000.0
    symbols = ['VOO']
    
    results_summary = []
    
    for threshold in crash_thresholds:
        logger.info(f"Testing crash threshold: {threshold:.1%}")
        
        # Modify config for this test
        test_config = config.copy()
        for symbol in symbols:
            if symbol in test_config.get('etfs', {}):
                test_config['etfs'][symbol]['strategy']['crash']['panic_threshold'] = threshold
        
        # Run backtest
        data_loader = HistoricalDataLoader()
        engine = BacktestEngine(test_config, data_loader)
        
        try:
            strategy_results = engine.run_backtest(symbols, start_date, end_date, initial_cash)
            
            if 'portfolio' in strategy_results:
                portfolio = strategy_results['portfolio']
                results_summary.append({
                    'crash_threshold': threshold,
                    'final_value': portfolio['final_value'],
                    'total_return': portfolio['total_return'],
                    'num_trades': len(portfolio['transactions']),
                    'total_invested': portfolio['total_invested']
                })
        
        except Exception as e:
            logger.error(f"Failed backtest for threshold {threshold}: {e}")
    
    # Print sensitivity analysis results
    print("\n" + "="*60)
    print("PARAMETER SENSITIVITY ANALYSIS")
    print("="*60)
    print("Crash Threshold | Final Value | Total Return | Trades | Invested")
    print("-" * 60)
    
    for result in results_summary:
        print(f"{result['crash_threshold']:>13.1%} | "
              f"${result['final_value']:>10,.0f} | "
              f"{result['total_return']:>10.1%} | "
              f"{result['num_trades']:>6} | "
              f"${result['total_invested']:>8,.0f}")
    
    print("="*60)


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        command = sys.argv[1].lower()
        
        if command == "custom":
            run_custom_backtest()
        elif command == "sensitivity":
            run_parameter_sensitivity_analysis()
        elif command == "analyze" and len(sys.argv) > 2:
            analyze_existing_results(sys.argv[2])
        else:
            print("Usage:")
            print("  python backtest_example.py custom          # Run custom backtest")
            print("  python backtest_example.py sensitivity     # Run parameter sensitivity analysis")
            print("  python backtest_example.py analyze <file>  # Analyze existing results file")
    else:
        # Default: run custom backtest
        run_custom_backtest()
