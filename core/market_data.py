import json
import time
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional

import requests

from .config import Settings


class MarketDataService:
    def __init__(self, settings: Settings):
        self.settings = settings
        self._orderbook_cache: Dict[str, Dict] = {}
        self._token_price_cache: Dict[str, Dict] = {}
        self._http_timeout = (5, 10)

    def get_active_markets(self, limit: int = 100, logger=None) -> List[Dict]:
        markets = self._fetch_gamma_markets(limit, logger)
        if not markets:
            return []

        now = datetime.now(timezone.utc)
        active_markets: List[Dict] = []

        for market in markets:
            if len(active_markets) >= limit:
                break
            if not isinstance(market, dict):
                continue
            if not self._is_market_tradeable(market, now):
                continue

            tokens = self._build_tokens(market)
            if not tokens:
                continue

            normalized_market = dict(market)
            normalized_market['tokens'] = tokens
            normalized_market.setdefault('accepting_orders', market.get('acceptingOrders'))
            normalized_market.setdefault('end_date_iso', market.get('endDateIso') or market.get('endDate'))
            normalized_market['volume'] = self._select_float(normalized_market, [
                'volume24hrClob', 'volumeNum', 'volume', 'volume24hr'
            ])
            normalized_market['liquidity'] = self._select_float(normalized_market, [
                'liquidityNum', 'liquidity', 'liquidityClob'
            ])
            active_markets.append(normalized_market)

        if not active_markets and logger:
            logger.warning("No tradeable markets returned from Gamma API")
            return []

        per_token_markets: List[Dict] = []
        for market in active_markets:
            tokens = market.get('tokens', [])
            for token in tokens:
                entry = dict(market)
                entry['token_id'] = token.get('token_id')
                entry['outcome'] = token.get('outcome')
                entry['token_outcome'] = token.get('outcome')
                entry['price'] = token.get('price')
                entry['token_price'] = token.get('price')
                entry['best_bid'] = token.get('best_bid')
                entry['best_ask'] = token.get('best_ask')
                entry['orderbook'] = token.get('orderbook')
                per_token_markets.append(entry)

        return per_token_markets[:limit]

    def get_market_price(self, token_id: str) -> Optional[float]:
        cached = self._token_price_cache.get(token_id)
        if cached and time.time() - cached['timestamp'] <= self.settings.cache_ttl:
            return float(cached['price'])

        book = self._fetch_orderbook(token_id)
        if not book:
            return None

        price = self._compute_mid_price(book)
        if price is None:
            return None

        self._token_price_cache[token_id] = {
            "price": price,
            "timestamp": time.time(),
        }
        return price

    def _fetch_gamma_markets(self, limit: int, logger=None) -> List[Dict]:
        try:
            query_limit = min(max(limit * 2, 20), 100)
            params = {
                "active": True,
                "closed": False,
                "archived": False,
                "enableOrderBook": True,
                "order": self.settings.market_order_field,
                "ascending": False,
                "limit": query_limit,
            }
            start_min = datetime.now(timezone.utc) - timedelta(days=self.settings.lookback_days)
            params["start_date_min"] = start_min.isoformat().replace("+00:00", "Z")

            response = requests.get(
                f"{self.settings.gamma_host}/markets",
                params=params,
                timeout=self._http_timeout,
            )
            response.raise_for_status()
            data = response.json()
            if isinstance(data, list):
                return data
            if isinstance(data, dict):
                return data.get('data', [])
            if logger:
                logger.error(f"Unexpected Gamma response type: {type(data)}")
            return []
        except Exception as exc:
            if logger:
                logger.error(f"Error fetching markets from Gamma API: {exc}")
            return []

    def _build_tokens(self, market: Dict) -> List[Dict]:
        tokens_out: List[Dict] = []
        raw_tokens = market.get('tokens') or []
        clob_token_ids = self._parse_json_list(market.get('clobTokenIds'))
        outcomes = self._parse_json_list(market.get('outcomes'))

        if not raw_tokens and clob_token_ids and outcomes:
            raw_tokens = []
            for idx, token_id in enumerate(clob_token_ids):
                token = {
                    "token_id": token_id,
                    "outcome": outcomes[idx] if idx < len(outcomes) else None,
                }
                raw_tokens.append(token)

        for token in raw_tokens:
            token_id = token.get('token_id') or token.get('id')
            if not token_id:
                continue
            orderbook = self._fetch_orderbook(token_id)
            if not orderbook:
                continue
            best_bid = self._top_price(orderbook.get('bids'))
            best_ask = self._top_price(orderbook.get('asks'))
            price = self._compute_mid_price(orderbook)
            tokens_out.append({
                "token_id": token_id,
                "outcome": token.get('outcome') or token.get('ticker'),
                "best_bid": best_bid,
                "best_ask": best_ask,
                "price": price,
                "orderbook": orderbook,
            })
        return tokens_out

    def _fetch_orderbook(self, token_id: str) -> Optional[Dict]:
        cached = self._orderbook_cache.get(token_id)
        if cached and time.time() - cached['timestamp'] <= self.settings.cache_ttl:
            return cached['orderbook']

        try:
            response = requests.get(
                f"{self.settings.clob_host}/book",
                params={"token_id": token_id, "limit": self.settings.orderbook_limit},
                timeout=self._http_timeout,
            )
            response.raise_for_status()
            data = response.json()
            orderbook = data.get('book') if 'book' in data else data
            if not orderbook:
                return None
            self._orderbook_cache[token_id] = {
                "orderbook": orderbook,
                "timestamp": time.time(),
            }
            return orderbook
        except Exception:
            return None

    def _compute_mid_price(self, orderbook: Dict) -> Optional[float]:
        best_bid = self._top_price(orderbook.get('bids'))
        best_ask = self._top_price(orderbook.get('asks'))
        if best_bid is None and best_ask is None:
            return None
        if best_bid is None:
            return best_ask
        if best_ask is None:
            return best_bid
        return (best_bid + best_ask) / 2

    def _top_price(self, levels) -> Optional[float]:
        if not levels:
            return None
        level = levels[0]
        if isinstance(level, dict):
            price = level.get('price')
        else:
            price = level[0] if isinstance(level, (list, tuple)) else None
        try:
            return float(price)
        except (TypeError, ValueError):
            return None

    def _is_market_tradeable(self, market: Dict, now: datetime) -> bool:
        if market.get('active') is False:
            return False
        if market.get('closed') is True:
            return False
        if market.get('archived') is True:
            return False
        if market.get('enableOrderBook') is False:
            return False
        accepting = market.get('acceptingOrders')
        if accepting is not None and not accepting:
            return False
        clob_token_ids = self._parse_json_list(market.get('clobTokenIds'))
        if len(clob_token_ids) == 0:
            return False
        end_str = market.get('endDateIso') or market.get('endDate')
        end_dt = self._parse_datetime(end_str)
        if end_dt and end_dt <= now:
            return False
        volume_value = self._select_float(market, [
            'volume24hrClob', 'volumeNum', 'volume24hr', 'volume24Hr', 'volume'
        ])
        if volume_value < self.settings.min_volume:
            return False
        return True

    def _parse_json_list(self, value) -> List:
        if isinstance(value, list):
            return value
        if isinstance(value, str):
            try:
                parsed = json.loads(value)
                if isinstance(parsed, list):
                    return parsed
            except json.JSONDecodeError:
                return []
        return []

    def _parse_datetime(self, value) -> Optional[datetime]:
        if not value:
            return None
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)
        except ValueError:
            return None

    def _to_float(self, value, default: float = 0.0) -> float:
        if value is None:
            return default
        if isinstance(value, (int, float)):
            return float(value)
        try:
            return float(str(value).replace(',', ''))
        except (TypeError, ValueError):
            return default

    def _select_float(self, market: Dict, keys: List[str], default: float = 0.0) -> float:
        for key in keys:
            if key in market:
                candidate = self._to_float(market.get(key), default)
                if candidate:
                    return candidate
        return default
