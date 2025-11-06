import os
from dataclasses import dataclass
from typing import Optional

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Settings:
    clob_host: str
    gamma_host: str
    chain_id: int
    private_key: Optional[str]
    funder_address: Optional[str]
    signature_type: int
    cache_ttl: int
    min_volume: float
    lookback_days: int
    market_order_field: str
    orderbook_limit: int


def get_settings() -> Settings:
    return Settings(
        clob_host=os.getenv("POLYMARKET_CLOB_URL", "https://clob.polymarket.com"),
        gamma_host=os.getenv("POLYMARKET_GAMMA_URL", "https://gamma-api.polymarket.com"),
        chain_id=int(os.getenv("POLYMARKET_CHAIN_ID", "137")),
        private_key=os.getenv("PRIVATE_KEY"),
        funder_address=os.getenv("POLYMARKET_PROXY_ADDRESS") or os.getenv("POLYMARKET_FUNDER_ADDRESS"),
        signature_type=int(os.getenv("POLYMARKET_SIGNATURE_TYPE", "0")),
        cache_ttl=int(os.getenv("POLYMARKET_CACHE_TTL", "30")),
        min_volume=float(os.getenv("POLYMARKET_MIN_VOLUME", "1000")),
        lookback_days=int(os.getenv("POLYMARKET_LOOKBACK_DAYS", "45")),
        market_order_field=os.getenv("POLYMARKET_MARKET_ORDER", "volume24hrClob"),
        orderbook_limit=int(os.getenv("POLYMARKET_ORDERBOOK_DEPTH", "50")),
    )
