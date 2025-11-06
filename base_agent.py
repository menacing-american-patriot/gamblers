import json
import os
import time
from abc import ABC, abstractmethod
from typing import Dict, List, Optional

from core import execution_service, hivemind, market_data_service, memory_store, portfolio, settings
from core.hivemind import FALLBACK_FLAG
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
        register_with_portfolio: bool = True,
    ):
        self.name = name
        self.requested_balance = float(initial_balance)
        self.initial_balance = 0.0
        self.current_balance = 0.0
        self.trades_made = 0
        self.winning_trades = 0
        self.losing_trades = 0

        self.settings = settings()
        self.market_service = market_service or market_data_service()
        self.execution_service = execution or execution_service()
        self.memory_store = memory or memory_store()
        self.portfolio = portfolio() if register_with_portfolio else None
        self.hivemind = hivemind()

        if self.portfolio is not None:
            allocated = self.portfolio.register_agent(self.name, self.requested_balance)
            self.initial_balance = allocated
            self.current_balance = allocated
        else:
            allocated = self.requested_balance
            self.initial_balance = self.requested_balance
            self.current_balance = self.requested_balance

        self.logger = get_logger(name)

        self._creds_warning_emitted = False
        self._ollama_client: Optional[OllamaClient] = None
        self._stop_requested = False

        agent_memory = self.memory_store.get_agent_memory(self.name)
        agent_memory.setdefault("allocation", allocated)
        agent_memory.setdefault("status", "initialized")
        agent_memory.setdefault("positions", {})
        agent_memory.setdefault("stats", [])

        if register_with_portfolio and allocated + 1e-9 < self.requested_balance:
            self.logger.warning(
                f"Allocated ${allocated:.2f} of requested ${self.requested_balance:.2f} due to treasury limits"
            )

        memory_positions = agent_memory.get("positions", {})
        if memory_positions and self.portfolio is not None:
            self.portfolio.reconcile_positions(self.name, memory_positions)

    def _reconcile_positions(self):
        if self.portfolio is None:
            return
        memory = self.memory_store.get_agent_memory(self.name)
        positions = memory.get("positions", {})
        if not positions:
            return
        self.portfolio.reconcile_positions(self.name, positions)

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
            if self.portfolio is None:
                self.logger.error("Portfolio not available for trading agent")
                return False

            validation = self.portfolio.validate_trade(
                agent_name=self.name,
                token_id=token_id,
                side=side_normalized,
                amount=amount,
                price=price,
            )
            if not validation.success:
                self.logger.warning(
                    f"Trade rejected: {validation.message} (token {token_id[:8]}, side {side_normalized}, amount {amount:.4f}, price {price})"
                )
                return False
            if amount <= 0:
                self.logger.warning("Bet amount must be positive")
                return False
            if amount < 1.0:
                self.logger.info(
                    f"Skipping trade below $1 minimum (amount={amount:.2f}, side={side_normalized}, token={token_id[:8]})"
                )
                return False
            if price is None or not (0.001 <= price <= 0.999):
                self.logger.warning(f"Skipping bet due to out-of-range price: {price}")
                return False

            agent_memory = self.memory_store.get_agent_memory(self.name)

            if self.execution_service.place_order(
                token_id=token_id,
                side=side_normalized,
                amount=amount,
                price=price,
                logger=self.logger,
            ):
                new_balance = self.portfolio.apply_trade(
                    agent_name=self.name,
                    token_id=token_id,
                    side=side_normalized,
                    amount=amount,
                    price=price,
                )
                self.current_balance = new_balance
                positions = self.portfolio.get_agent_positions(self.name)
                agent_memory["positions"] = positions
                shares = amount / price if price else 0.0
                agent_memory["last_trade"] = {
                    "token_id": token_id,
                    "side": side_normalized,
                    "amount": amount,
                    "price": price,
                    "shares": shares,
                    "timestamp": time.time(),
                }
                self.trades_made += 1
                return True
            return False
        except Exception as e:
            self.logger.error(f"Error placing bet: {e}")
            agent_memory = self.memory_store.get_agent_memory(self.name)
            agent_memory["last_error"] = str(e)
            return False
    
    def get_stats(self) -> Dict:
        if self.portfolio is not None:
            self.current_balance = self.portfolio.get_agent_balance(self.name)
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
        if self.portfolio is not None:
            self.current_balance = self.portfolio.get_agent_balance(self.name)
        self.logger.info(f"🚀 {self.name} starting with ${self.current_balance:.2f}")
        self._stop_requested = False
        agent_memory = self.memory_store.get_agent_memory(self.name)
        agent_memory["status"] = "running"
        agent_memory["iterations"] = 0
        self._reconcile_positions()
        positions_snapshot = agent_memory.get("positions", {})
        if positions_snapshot:
            self.logger.info(f"📦 Loaded existing positions: {positions_snapshot}")
        if not self.execution_service.trading_enabled and not self._creds_warning_emitted:
            self.logger.warning(
                "API credentials not configured; agent will operate in read-only mode without placing orders"
            )
            self._creds_warning_emitted = True
        
        iteration = 0
        while iteration < max_iterations and self.should_continue():
            if self._stop_requested:
                self.logger.info(f"⏹ {self.name} stop requested")
                break
            try:
                if self.portfolio is not None:
                    self.current_balance = self.portfolio.get_agent_balance(self.name)
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
                agent_memory["iterations"] = iteration
                iteration += 1
                
                if iteration < max_iterations and self.should_continue():
                    time.sleep(sleep_time)
                    
            except Exception as e:
                self.logger.error(f"Error in main loop: {e}")
                agent_memory["last_error"] = str(e)
                time.sleep(sleep_time)
        
        self.logger.info(f"🏁 {self.name} finished")
        self.log_stats()
        agent_memory["status"] = "stopped"
        return self.get_stats()

    def request_stop(self):
        self._stop_requested = True

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

    def manage_with_llm(self, market: Dict, proposal: Dict, tool_name: str) -> Optional[Dict]:
        if not proposal:
            return None

        memory = self.memory_store.get_agent_memory(self.name)
        positions = memory.get("positions", {})
        token_id = proposal.get("token_id", "")
        available_shares = positions.get(token_id, 0.0)

        if proposal.get("side", "").upper() == "SELL" and available_shares <= 1e-9:
            self.logger.info(
                f"Skipping SELL proposal from {tool_name} on {token_id[:8]} - no position held"
            )
            return None

        context = {
            "positions": positions,
            "balance": self.current_balance,
        }

        if self.hivemind and getattr(self.hivemind, "enabled", False):
            decision = self.hivemind.collaborative_decision(
                agent_name=self.name,
                market=market,
                proposal=proposal,
                context=context,
            )
            if decision is None:
                return None
            if isinstance(decision, dict) and decision.get(FALLBACK_FLAG):
                self.logger.debug("Hivemind fallback triggered; deferring to local LLM")
            else:
                return decision

        client = self.get_ollama_client()
        if not client:
            return proposal

        payload = {
            "agent": self.name,
            "tool": tool_name,
            "proposal": proposal,
            "portfolio_balance": self.current_balance,
            "positions": positions,
            "available_shares": available_shares,
            "market": {
                "question": market.get("question"),
                "outcome": market.get("outcome"),
                "price": market.get("price"),
                "best_bid": market.get("best_bid"),
                "best_ask": market.get("best_ask"),
                "volume": market.get("volume"),
                "liquidity": market.get("liquidity"),
                "category": market.get("category"),
            },
        }

        system_prompt = (
            "You are the decision layer for a trading agent on Polymarket. "
            "Assess the tool proposal and decide to EXECUTE or SKIP. If executing, you may adjust side, amount, or price but keep them within valid bounds (0 < price < 1, amount >= 0). "
            "NEVER approve a SELL when available_shares <= 0, and never increase amount beyond available_shares * price for sells. You cannot sell shares you have not bought!"
            "Respond with compact JSON: {\"action\": \"EXECUTE\"|\"SKIP\", \"side\": ..., \"amount\": ..., \"price\": ..., \"reasoning\": ...}."
        )

        prompt = (
            "Tool proposal:\n"
            f"{json.dumps(payload, ensure_ascii=False)}\n"
            "Return JSON only."
        )

        try:
            response = client.generate(prompt, system=system_prompt, max_tokens=256)
        except Exception as exc:
            self.logger.error(f"LLM decision failed: {exc}")
            return proposal

        data = None
        try:
            start = response.find("{")
            end = response.rfind("}")
            if start != -1 and end != -1:
                data = json.loads(response[start : end + 1])
        except Exception:
            data = None

        if data is None:
            force_json = os.getenv("LLM_FORCE_JSON", "true").lower() in {"1", "true", "yes"}
            if force_json:
                self.logger.error(f"Failed to parse LLM response in strict mode. Raw: {response[:120]}...")
                return proposal
            self.logger.debug(
                "LLM returned non-JSON response in tolerant mode; using original proposal"
            )
            return proposal

        action = str(data.get("action", "")).upper()
        if action != "EXECUTE":
            self.logger.info(f"LLM vetoed proposal from {tool_name}")
            return None

        updated = dict(proposal)
        if "side" in data and data["side"]:
            updated["side"] = str(data["side"]).upper()
        if "price" in data and data["price"] is not None:
            try:
                updated["price"] = float(data["price"])
            except (TypeError, ValueError):
                pass
        if "amount" in data and data["amount"] is not None:
            try:
                updated["amount"] = max(0.0, float(data["amount"]))
            except (TypeError, ValueError):
                pass

        reasoning = data.get("reasoning")
        if reasoning:
            self.logger.info(f"LLM reasoning ({tool_name}): {reasoning}")

        return updated
