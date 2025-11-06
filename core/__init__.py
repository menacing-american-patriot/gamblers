"""Core singletons and helpers for Polymarket agents."""

import os

from .config import Settings, get_settings
from .logging import get_logger
from .market_data import MarketDataService
from .execution import ExecutionService
from .memory import MemoryStore
from .portfolio import Portfolio
from .hivemind import get_hivemind

_settings = get_settings()
_market_data_service = MarketDataService(_settings)
_execution_service = ExecutionService(_settings)
_memory_store = MemoryStore()
_portfolio = Portfolio(float(os.getenv("PORTFOLIO_STARTING_CASH", "100")))
_hivemind = get_hivemind()


def settings() -> Settings:
    return _settings


def market_data_service() -> MarketDataService:
    return _market_data_service


def execution_service() -> ExecutionService:
    return _execution_service


def memory_store() -> MemoryStore:
    return _memory_store


def portfolio() -> Portfolio:
    return _portfolio


def hivemind():
    return _hivemind
