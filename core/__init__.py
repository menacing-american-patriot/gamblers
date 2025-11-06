"""Core singletons and helpers for Polymarket agents."""

from .config import Settings, get_settings
from .logging import get_logger
from .market_data import MarketDataService
from .execution import ExecutionService
from .memory import MemoryStore

_settings = get_settings()
_market_data_service = MarketDataService(_settings)
_execution_service = ExecutionService(_settings)
_memory_store = MemoryStore()


def settings() -> Settings:
    return _settings


def market_data_service() -> MarketDataService:
    return _market_data_service


def execution_service() -> ExecutionService:
    return _execution_service


def memory_store() -> MemoryStore:
    return _memory_store
