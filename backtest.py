import logging
from utils.config_loader import load_config

logger = logging.getLogger(__name__)


def run_backtest() -> None:
    config = load_config()
    logger.info("Backtest harness stub - config loaded for %d ETFs", len((config or {}).get("etfs", {})))


