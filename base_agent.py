import os
import time
from abc import ABC, abstractmethod
from typing import Dict, List, Optional

from core import execution_service, market_data_service, memory_store, settings
from core.logging import get_logger
from ollama_client import OllamaClient


class BaseAgent(ABC):
    def __init__(
        self,
        name: str,
        initial_balance: float,
        *,
        market_service=None,
        execution=None,
        memory=None,
    ):
        self.name = name
        self.initial_balance = initial_balance
        self.current_balance = initial_balance
        self.trades_made = 0
        self.winning_trades = 0
        self.losing_trades = 0

        self.settings = settings()
        self.market_service = market_service or market_data_service()
        self.execution_service = execution or execution_service()
        self.memory_store = memory or memory_store()

        self.logger = get_logger(name)

        self._creds_warning_emitted = False
        self._ollama_client: Optional[OllamaClient] = None

    def get_active_markets(self, limit: int = 100) -> List[Dict]:
        return self.market_service.get_active_markets(limit=limit, logger=self.logger)

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
            return self.market_service.get_market_price(token_id)
        except Exception as e:
            self.logger.error(f"Error fetching price for {token_id}: {e}")
            return None
    
    def place_bet(self, token_id: str, side: str, amount: float, price: float) -> bool:
        try:
            side_normalized = (side or "").upper()
            if side_normalized not in {"BUY", "SELL"}:
                self.logger.warning(f"Unknown side '{side}' supplied; skipping trade")
                return False

            if side_normalized == "BUY" and amount > self.current_balance:
                self.logger.warning(
                    f"Insufficient balance for bet: ${amount:.2f} > ${self.current_balance:.2f}"
                )
                return False
            if amount <= 0:
                self.logger.warning("Bet amount must be positive")
                return False
            if price is None or not (0.001 <= price <= 0.999):
                self.logger.warning(f"Skipping bet due to out-of-range price: {price}")
                return False

            agent_memory = self.memory_store.get_agent_memory(self.name)
            positions: Dict[str, float] = agent_memory.setdefault("positions", {})
            shares = amount / price

            current_shares = positions.get(token_id, 0.0)
            if side_normalized == "SELL":
                if current_shares <= 1e-9:
                    self.logger.warning(
                        f"Cannot SELL {token_id[:8]} – no existing position"
                    )
                    return False
                if current_shares + 1e-9 < shares:
                    self.logger.warning(
                        f"Cannot SELL {shares:.4f} shares of {token_id[:8]} – holdings only {current_shares:.4f}"
                    )
                    return False

            if self.execution_service.place_order(
                token_id=token_id,
                side=side_normalized,
                amount=amount,
                price=price,
                logger=self.logger,
            ):
                if side_normalized == "BUY":
                    self.current_balance -= amount
                    positions[token_id] = current_shares + shares
                else:
                    self.current_balance += amount
                    positions[token_id] = max(0.0, current_shares - shares)
                agent_memory["last_trade"] = {
                    "token_id": token_id,
                    "side": side_normalized,
                    "amount": amount,
                    "price": price,
                    "shares": shares,
                }
                self.trades_made += 1
                return True
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
        self.memory_store.append_agent_history(self.name, "stats", stats)
    
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
        if not self.execution_service.trading_enabled and not self._creds_warning_emitted:
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

    def get_ollama_client(self) -> Optional[OllamaClient]:
        if self._ollama_client is not None:
            return self._ollama_client
        model = os.getenv("OLLAMA_MODEL")
        if not model:
            return None
        host = os.getenv("OLLAMA_HOST")
        timeout_env = os.getenv("OLLAMA_TIMEOUT")
        try:
            timeout = float(timeout_env) if timeout_env is not None else None
        except ValueError:
            timeout = None
        try:
            self._ollama_client = OllamaClient(host=host, model=model, timeout=timeout)
            return self._ollama_client
        except Exception as exc:
            self.logger.error(f"Failed to initialize Ollama client: {exc}")
            self._ollama_client = None
            return None
