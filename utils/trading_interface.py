from abc import ABC, abstractmethod
from typing import List, Dict, Union, Optional
from datetime import datetime

class TradingInterface(ABC):
    """Abstract base class defining the interface for broker API interactions."""
    
    @abstractmethod
    def login(self, **credentials) -> bool:
        """Login to the trading platform."""
        pass
    
    @abstractmethod
    def logout(self) -> None:
        """Logout from the trading platform."""
        pass
    
    @abstractmethod
    def get_cash_balance(self) -> float:
        """Get available cash balance."""
        pass
    
    @abstractmethod
    def get_latest_price(self, ticker: str) -> float:
        """Get latest price for a given ticker."""
        pass
    
    @abstractmethod
    def place_market_buy(self, ticker: str, quantity: float) -> Dict:
        """Place a market buy order."""
        pass
    
    @abstractmethod
    def get_recent_orders(self, ticker: str, days: int = 7) -> List[Dict]:
        """Get recent orders for a given ticker."""
        pass
    
    @abstractmethod
    def get_weekly_spent(self, ticker: str) -> float:
        """Calculate total amount spent on a ticker in the past week."""
        pass 