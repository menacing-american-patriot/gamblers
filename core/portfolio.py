from __future__ import annotations

import threading
from collections import defaultdict
from dataclasses import dataclass
from typing import Dict, Optional, Tuple


@dataclass
class TradeValidation:
    success: bool
    message: str = ""


class Portfolio:
    def __init__(self, starting_cash: float = 100.0):
        self.starting_cash = float(starting_cash)
        self._cash_reserve = float(starting_cash)
        self._agent_balances: Dict[str, float] = {}
        self._agent_positions: Dict[str, Dict[str, float]] = defaultdict(lambda: defaultdict(float))
        self._positions: Dict[str, float] = defaultdict(float)
        self._lock = threading.Lock()

    # --- Registration & balances -------------------------------------------------

    def register_agent(self, agent_name: str, desired_allocation: float) -> float:
        with self._lock:
            if agent_name in self._agent_balances:
                return self._agent_balances[agent_name]

            allocation = float(max(0.0, desired_allocation))
            allocation = min(allocation, self._cash_reserve)
            self._cash_reserve -= allocation
            self._agent_balances[agent_name] = allocation
            return allocation

    def get_agent_balance(self, agent_name: str) -> float:
        with self._lock:
            return self._agent_balances.get(agent_name, 0.0)

    def get_agent_positions(self, agent_name: str) -> Dict[str, float]:
        with self._lock:
            return dict(self._agent_positions.get(agent_name, {}))

    def get_total_cash(self) -> float:
        with self._lock:
            return self._cash_reserve + sum(self._agent_balances.values())

    def get_available_cash(self) -> float:
        with self._lock:
            return self._cash_reserve

    def summary(self) -> Dict[str, float]:
        with self._lock:
            allocated = sum(self._agent_balances.values())
            return {
                "starting_cash": self.starting_cash,
                "available_cash": self._cash_reserve,
                "allocated_cash": allocated,
                "total_cash": self._cash_reserve + allocated,
            }

    # --- Trade lifecycle ---------------------------------------------------------

    def validate_trade(
        self,
        agent_name: str,
        token_id: str,
        side: str,
        amount: float,
        price: float,
    ) -> TradeValidation:
        side_norm = side.upper()
        shares = amount / price if price else 0.0
        with self._lock:
            balance = self._agent_balances.get(agent_name, 0.0)
            if side_norm == "BUY":
                if amount > balance + 1e-9:
                    return TradeValidation(False, "Insufficient allocated funds")
                if amount <= 0:
                    return TradeValidation(False, "Amount must be positive")
            elif side_norm == "SELL":
                holding = self._agent_positions[agent_name].get(token_id, 0.0)
                if shares > holding + 1e-9:
                    return TradeValidation(False, "Insufficient position to sell")
            else:
                return TradeValidation(False, f"Unknown side '{side}'")
        return TradeValidation(True, "")

    def apply_trade(
        self,
        agent_name: str,
        token_id: str,
        side: str,
        amount: float,
        price: float,
    ) -> float:
        side_norm = side.upper()
        shares = amount / price if price else 0.0
        with self._lock:
            if side_norm == "BUY":
                self._agent_balances[agent_name] -= amount
                self._agent_positions[agent_name][token_id] += shares
                self._positions[token_id] += shares
            elif side_norm == "SELL":
                self._agent_balances[agent_name] += amount
                self._agent_positions[agent_name][token_id] = max(
                    0.0, self._agent_positions[agent_name][token_id] - shares
                )
                self._positions[token_id] = max(0.0, self._positions[token_id] - shares)
            return self._agent_balances[agent_name]

    def reconcile_positions(self, agent_name: str, positions: Dict[str, float]) -> None:
        with self._lock:
            for token_id, shares in positions.items():
                if shares <= 0:
                    continue
                self._agent_positions[agent_name][token_id] = shares
                self._positions[token_id] += shares
