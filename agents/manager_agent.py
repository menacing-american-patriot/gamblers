import os
from typing import Dict, Optional

from base_agent import BaseAgent
from core.tools import ToolResult, get_tool_signals


class ManagerAgent(BaseAgent):
    def __init__(self, initial_balance: float = 25.0, name: Optional[str] = None):
        agent_name = name or os.getenv("MANAGER_AGENT_NAME", "ManagerAgent")
        super().__init__(agent_name, initial_balance)
        self.min_balance_pct = float(os.getenv("MANAGER_MIN_BALANCE_PCT", "0.05"))
        self.max_bet_pct = float(os.getenv("MANAGER_MAX_BET_PCT", "0.35"))
        self.default_bet_pct = float(os.getenv("MANAGER_DEFAULT_BET_PCT", "0.18"))
        self.confidence_threshold = float(os.getenv("MANAGER_CONFIDENCE_THRESHOLD", "0.58"))

    def analyze_market(self, market: Dict) -> Optional[Dict]:
        memory = self.memory_store.get_agent_memory(self.name)
        tool_scores: Dict[str, float] = memory.setdefault("tool_scores", {})
        signals = get_tool_signals(self.name, market, self.current_balance)

        best_name = None
        best_score = 0.0
        best_signal: Optional[ToolResult] = None

        for name, signal in signals.items():
            if not signal or not signal.side:
                continue
            base_score = tool_scores.get(name, 0.5)
            combined = 0.5 * base_score + 0.5 * signal.confidence
            if combined > best_score:
                best_score = combined
                best_name = name
                best_signal = signal

        if not best_signal or best_signal.confidence < self.confidence_threshold:
            return None

        bet_pct = best_signal.bet_pct or self.default_bet_pct
        bet_pct = max(0.01, min(bet_pct, self.max_bet_pct))
        amount = min(self.current_balance * bet_pct, self.current_balance * 0.9)
        price = best_signal.price or market.get("price")
        token_id = market.get("token_id")

        if not token_id or price is None or amount <= 0:
            return None

        tool_scores[best_name] = min(1.0, best_score)
        memory["last_tool"] = {
            "tool": best_name,
            "confidence": best_signal.confidence,
            "bet_pct": bet_pct,
        }

        return {
            "token_id": token_id,
            "side": best_signal.side,
            "amount": amount,
            "price": float(price),
        }

    def should_continue(self) -> bool:
        return self.current_balance >= self.initial_balance * self.min_balance_pct
