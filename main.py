import logging
import argparse
import os
from datetime import datetime, time
from zoneinfo import ZoneInfo
from dotenv import load_dotenv

from state import init_db
from measure import run_weekly_measurement
from backtest import run_backtest
from runner import run_drip, run_eod, run_rth

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        # logging.FileHandler("bot.log"),
        logging.StreamHandler()
    ]
)

def main():
    """
    Main entry point to run dip buying bot
    """
    parser = argparse.ArgumentParser(description="Dip-Buying Bot")
    parser.add_argument(
        "--mode",
        required=False,
        default="auto",
        choices=["auto", "post_crash_drip", "eod", "measure", "backtest"],
        help="Run mode (default: auto)"
    )
    args = parser.parse_args()

    load_dotenv()
    init_db()

    if args.mode == "measure":
        run_weekly_measurement()
        return

    if args.mode == "backtest":
        run_backtest()
        return

    if args.mode == "auto":
        # Choose mode based on US/Eastern session windows
        now_et = datetime.now(ZoneInfo("America/New_York"))
        is_weekday = now_et.weekday() < 5  # 0=Mon .. 4=Fri

        def between(start_h, start_m, end_h, end_m):
            start = time(hour=start_h, minute=start_m)
            end = time(hour=end_h, minute=end_m)
            return start <= now_et.time() < end

        # EOD window: last 15 minutes before close (approx 15:45-16:00 ET)
        if is_weekday and between(15, 45, 16, 0):
            run_eod()
            return

        # Drip window: midday single run (12:00-12:30 ET)
        if is_weekday and between(12, 0, 12, 30):
            run_drip()
            return

        run_rth()
            

        # If nothing matched (weekends/overnight), do nothing gracefully
        logging.info("Auto mode: outside trading windows; no action taken.")
        return

    if args.mode == "post_crash_drip":
        run_drip()
        return
    if args.mode == "eod":
        run_eod()
        return

if __name__ == "__main__":
    main()