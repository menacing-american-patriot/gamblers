import os
import json
import logging
import time
from abc import ABC, abstractmethod
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Optional

import requests
from py_clob_client.client import ClobClient
from py_clob_client.clob_types import OrderArgs, OrderType, ApiCreds

class BaseAgent(ABC):
    def __init__(self, name: str, initial_balance: float, host: str = "https://clob.polymarket.com"):
        self.name = name
        self.initial_balance = initial_balance
        self.current_balance = initial_balance
        self.host = host
        self.trades_made = 0
        self.winning_trades = 0
        self.losing_trades = 0
        
        self.logger = logging.getLogger(name)
        self.logger.setLevel(logging.INFO)
        
        os.makedirs("agent_logs", exist_ok=True)
        fh = logging.FileHandler(f"agent_logs/{name}.log")
        fh.setLevel(logging.INFO)
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        fh.setFormatter(formatter)
        self.logger.addHandler(fh)
        
        ch = logging.StreamHandler()
        ch.setLevel(logging.INFO)
        ch.setFormatter(formatter)
        self.logger.addHandler(ch)
        
        self.trading_enabled = False
        self._creds_warning_emitted = False
        self._creds_error_emitted = False
        self.client = None
        self._init_client()
        self.gamma_base_url = os.getenv("POLYMARKET_GAMMA_URL", "https://gamma-api.polymarket.com")
        self.clob_base_url = os.getenv("POLYMARKET_CLOB_URL", "https://clob.polymarket.com")
        self._orderbook_cache: Dict[str, Dict] = {}
        self._token_price_cache: Dict[str, Dict] = {}
        self._cache_ttl = int(os.getenv("POLYMARKET_CACHE_TTL", "30"))
        self._http_timeout = (5, 10)
        
    def _init_client(self):
        try:
            private_key = os.getenv("PRIVATE_KEY")
            if not private_key:
                raise ValueError("PRIVATE_KEY not found in environment")
            
            self.client = ClobClient(
                self.host,
                key=private_key,
                chain_id=137
            )
            self.logger.info(f"{self.name} initialized successfully")
            self._configure_api_credentials()
        except Exception as e:
            self.logger.error(f"Failed to initialize client: {e}")
            raise

    def _configure_api_credentials(self):
        api_key = os.getenv("POLY_API_KEY") or os.getenv("CLOB_API_KEY")
        api_secret = os.getenv("POLY_API_SECRET") or os.getenv("CLOB_API_SECRET")
        api_passphrase = os.getenv("POLY_API_PASSPHRASE") or os.getenv("CLOB_API_PASSPHRASE")

        if api_key and api_secret and api_passphrase:
            try:
                creds = ApiCreds(
                    api_key=api_key,
                    api_secret=api_secret,
                    api_passphrase=api_passphrase,
                )
                self.client.set_api_creds(creds)
                self.trading_enabled = True
                self.logger.info("Level 2 API credentials loaded; trading enabled")
            except Exception as exc:
                self.trading_enabled = False
                self.logger.error(f"Failed to apply API credentials: {exc}")
        else:
            self.trading_enabled = False
    
    def get_active_markets(self, limit: int = 100) -> List[Dict]:
        markets = self._fetch_gamma_markets(limit)
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

        if not active_markets:
            self.logger.warning("No tradeable markets returned from Gamma API")
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

    def _fetch_gamma_markets(self, limit: int) -> List[Dict]:
        try:
            query_limit = min(max(limit * 2, 20), 100)
            order_field = os.getenv("POLYMARKET_MARKET_ORDER", "volume24hrClob")
            params = {
                "active": True,
                "closed": False,
                "archived": False,
                "enableOrderBook": True,
                "order": order_field,
                "ascending": False,
                "limit": query_limit,
            }
            lookback_days = int(os.getenv("POLYMARKET_LOOKBACK_DAYS", "45"))
            start_min = datetime.now(timezone.utc) - timedelta(days=lookback_days)
            params["start_date_min"] = start_min.isoformat().replace("+00:00", "Z")

            response = requests.get(
                f"{self.gamma_base_url}/markets",
                params=params,
                timeout=self._http_timeout,
            )
            response.raise_for_status()

            data = response.json()
            if isinstance(data, list):
                return data
            if isinstance(data, dict):
                return data.get('data', [])
            self.logger.error(f"Unexpected Gamma response type: {type(data)}")
            return []
        except Exception as e:
            self.logger.error(f"Error fetching markets from Gamma API: {e}")
            return []
    
    def get_market_price(self, token_id: str, market: Dict = None) -> Optional[float]:
        """Get price for a token, either from market data or order book"""
        try:
            # First try to get price from direct market fields
            if market:
                direct_price = market.get('price') or market.get('token_price')
                if direct_price is not None:
                    return float(direct_price)

            # Next try to get price from market data tokens if provided
            if market and 'tokens' in market:
                for token in market['tokens']:
                    if token.get('token_id') == token_id:
                        price = token.get('price')
                        if price is not None:
                            return float(price)
            
            cached = self._token_price_cache.get(token_id)
            if cached and time.time() - cached['timestamp'] <= self._cache_ttl:
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
        except Exception as e:
            self.logger.error(f"Error fetching price for {token_id}: {e}")
            return None
    
    def place_bet(self, token_id: str, side: str, amount: float, price: float) -> bool:
        try:
            if not self.trading_enabled:
                if not self._creds_error_emitted:
                    self.logger.error(
                        "API credentials missing; set POLY_API_KEY, POLY_API_SECRET, and POLY_API_PASSPHRASE to enable trading"
                    )
                    self._creds_error_emitted = True
                return False
            if amount > self.current_balance:
                self.logger.warning(f"Insufficient balance for bet: ${amount:.2f} > ${self.current_balance:.2f}")
                return False
            if amount <= 0:
                self.logger.warning("Bet amount must be positive")
                return False
            if price is None or not (0.001 <= price <= 0.999):
                self.logger.warning(f"Skipping bet due to out-of-range price: {price}")
                return False
            
            order_args = OrderArgs(
                token_id=token_id,
                price=price,
                size=amount / price,
                side=side,
                fee_rate_bps=0
            )
            
            signed_order = self.client.create_order(order_args)
            resp = self.client.post_order(signed_order, OrderType.GTC)
            
            if resp and resp.get('success'):
                self.current_balance -= amount
                self.trades_made += 1
                self.logger.info(f"✓ Placed {side} bet: ${amount:.2f} @ {price:.3f} on {token_id[:8]}...")
                return True
            else:
                self.logger.warning(f"Order placement failed: {resp}")
                return False
                
        except Exception as e:
            self.logger.error(f"Error placing bet: {e}")
            return False
    
    def get_stats(self) -> Dict:
        profit = self.current_balance - self.initial_balance
        roi = (profit / self.initial_balance * 100) if self.initial_balance > 0 else 0
        
        return {
            "name": self.name,
            "initial_balance": self.initial_balance,
            "current_balance": self.current_balance,
            "profit": profit,
            "roi": roi,
            "trades_made": self.trades_made,
            "winning_trades": self.winning_trades,
            "losing_trades": self.losing_trades
        }
    
    def log_stats(self):
        stats = self.get_stats()
        self.logger.info(f"📊 Stats - Balance: ${stats['current_balance']:.2f} | "
                        f"P/L: ${stats['profit']:.2f} ({stats['roi']:.1f}%) | "
                        f"Trades: {stats['trades_made']}")
    
    @abstractmethod
    def analyze_market(self, market: Dict) -> Optional[Dict]:
        """
        Analyze a market and return betting decision
        Market has 'tokens' array with token_id and current price
        Returns: {"token_id": str, "side": "BUY"/"SELL", "amount": float, "price": float} or None
        """
        pass
    
    @abstractmethod
    def should_continue(self) -> bool:
        """Determine if agent should continue trading"""
        pass
    
    def run(self, max_iterations: int = 50, sleep_time: int = 30):
        self.logger.info(f"🚀 {self.name} starting with ${self.initial_balance:.2f}")
        if not self.trading_enabled and not self._creds_warning_emitted:
            self.logger.warning(
                "API credentials not configured; agent will operate in read-only mode without placing orders"
            )
            self._creds_warning_emitted = True
        
        iteration = 0
        while iteration < max_iterations and self.should_continue():
            try:
                markets = self.get_active_markets()
                if not markets:
                    self.logger.warning("No active markets found")
                    time.sleep(sleep_time)
                    continue
                
                for market in markets:
                    if not self.should_continue():
                        break
                    
                    decision = self.analyze_market(market)
                    if decision:
                        self.place_bet(
                            decision['token_id'],
                            decision['side'],
                            decision['amount'],
                            decision['price']
                        )
                        time.sleep(2)
                
                self.log_stats()
                iteration += 1
                
                if iteration < max_iterations and self.should_continue():
                    time.sleep(sleep_time)
                    
            except Exception as e:
                self.logger.error(f"Error in main loop: {e}")
                time.sleep(sleep_time)
        
        self.logger.info(f"🏁 {self.name} finished")
        self.log_stats()
        return self.get_stats()

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
        min_volume = float(os.getenv("POLYMARKET_MIN_VOLUME", "1000"))
        if volume_value < min_volume:
            return False

        return True

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
                return self._to_float(market.get(key), default)
        return default

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

    def _parse_datetime(self, value: Optional[str]) -> Optional[datetime]:
        if not value:
            return None
        try:
            cleaned = value.replace('Z', '+00:00') if isinstance(value, str) else value
            dt = datetime.fromisoformat(cleaned)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except (ValueError, AttributeError):
            return None

    def _fetch_orderbook(self, token_id: str) -> Optional[Dict]:
        now_ts = time.time()
        cached = self._orderbook_cache.get(token_id)
        if cached and now_ts - cached['timestamp'] <= self._cache_ttl:
            return cached['data']

        try:
            response = requests.get(
                f"{self.clob_base_url}/book",
                params={"token_id": token_id},
                timeout=self._http_timeout,
            )
            if response.status_code != 200:
                return None
            book = response.json()
            bids = book.get('bids') or []
            asks = book.get('asks') or []
            if not bids and not asks:
                return None
            self._orderbook_cache[token_id] = {
                "timestamp": now_ts,
                "data": book,
            }
            return book
        except requests.RequestException:
            return None

    def _compute_mid_price(self, orderbook: Dict) -> Optional[float]:
        best_bid = self._top_price(orderbook.get('bids'), side='bid')
        best_ask = self._top_price(orderbook.get('asks'), side='ask')

        if best_bid is None and best_ask is None:
            return None
        if best_bid is None:
            return best_ask
        if best_ask is None:
            return best_bid
        return (best_bid + best_ask) / 2

    def _top_price(self, levels, side: str) -> Optional[float]:
        if not levels:
            return None
        try:
            prices = [float(level['price']) for level in levels if 'price' in level]
            if not prices:
                return None
            return max(prices) if side == 'bid' else min(prices)
        except (TypeError, ValueError):
            return None

    def _build_tokens(self, market: Dict) -> List[Dict]:
        outcomes = self._parse_json_list(market.get('outcomes'))
        token_ids = self._parse_json_list(market.get('clobTokenIds'))

        if not token_ids:
            return []

        tokens: List[Dict] = []
        for idx, token_id in enumerate(token_ids):
            orderbook = self._fetch_orderbook(token_id)
            if not orderbook:
                continue

            best_bid = self._top_price(orderbook.get('bids'), side='bid')
            best_ask = self._top_price(orderbook.get('asks'), side='ask')

            price = self._compute_mid_price(orderbook)
            if price is None or not (0.0 < price < 1.0):
                continue

            outcome_label = outcomes[idx] if idx < len(outcomes) else f"Outcome {idx + 1}"

            trimmed_book = {
                "market": orderbook.get('market'),
                "asset_id": orderbook.get('asset_id'),
                "timestamp": orderbook.get('timestamp'),
                "min_order_size": orderbook.get('min_order_size'),
                "tick_size": orderbook.get('tick_size'),
                "neg_risk": orderbook.get('neg_risk'),
                "bids": (orderbook.get('bids') or [])[:5],
                "asks": (orderbook.get('asks') or [])[:5],
            }

            token_payload = {
                "token_id": token_id,
                "outcome": outcome_label,
                "price": price,
                "best_bid": best_bid,
                "best_ask": best_ask,
                "orderbook": trimmed_book,
            }

            self._token_price_cache[token_id] = {
                "price": price,
                "timestamp": time.time(),
            }

            tokens.append(token_payload)

        return tokens
