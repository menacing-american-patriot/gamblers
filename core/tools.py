from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional, Protocol

from core import memory_store


@dataclass
class ToolContext:
    agent_name: str
    market: Dict
    balance: float
    memory: Dict


@dataclass
class ToolResult:
    side: Optional[str]
    confidence: float = 0.5
    price: Optional[float] = None
    bet_pct: Optional[float] = None
    reasoning: Optional[str] = None


class Tool(Protocol):
    name: str

    def evaluate(self, context: ToolContext) -> Optional[ToolResult]: ...


class AgentTool:
    def __init__(self, name: str, agent_cls):
        self.name = name
        self._agent_cls = agent_cls
        self._agent = None

    def _get_agent(self, initial_balance: float):
        if self._agent is None:
            self._agent = self._agent_cls(initial_balance=initial_balance)
            self._agent.logger.disabled = True
        self._agent.current_balance = initial_balance
        return self._agent

    def evaluate(self, context: ToolContext) -> Optional[ToolResult]:
        agent = self._get_agent(context.balance)
        decision = agent.analyze_market(context.market)
        if not decision:
            return None
        side = decision.get("side")
        price = decision.get("price")
        amount = decision.get("amount")
        bet_pct = None
        if amount and context.balance > 0:
            bet_pct = min(1.0, amount / context.balance)
        return ToolResult(
            side=side,
            confidence=0.6,
            price=price,
            bet_pct=bet_pct,
        )


class ToolRegistry:
    def __init__(self):
        self._tools: Dict[str, Tool] = {}

    def register(self, tool: Tool):
        self._tools[tool.name] = tool

    def evaluate_all(self, context: ToolContext) -> Dict[str, Optional[ToolResult]]:
        results: Dict[str, Optional[ToolResult]] = {}
        for name, tool in self._tools.items():
            try:
                results[name] = tool.evaluate(context)
            except Exception as exc:
                results[name] = None
        return results

    def tools(self) -> Dict[str, Tool]:
        return dict(self._tools)


_TOOL_REGISTRY: Optional[ToolRegistry] = None
_DEFAULT_REGISTERED = False


def get_tool_registry() -> ToolRegistry:
    global _TOOL_REGISTRY
    if _TOOL_REGISTRY is None:
        _TOOL_REGISTRY = ToolRegistry()
    return _TOOL_REGISTRY


def register_default_tools():
    global _DEFAULT_REGISTERED
    if _DEFAULT_REGISTERED:
        return
    registry = get_tool_registry()
    from agents.momentum_chaser import MomentumChaser
    from agents.arbitrage_hunter import ArbitrageHunter
    from agents.neural_predictor import NeuralPredictor
    from agents.news_sentiment_trader import NewsSentimentTrader
    from agents.whale_follower import WhaleFollower
    from agents.scalper import Scalper

    default_tools = {
        "MomentumChaser": MomentumChaser,
        "ArbitrageHunter": ArbitrageHunter,
        "NeuralPredictor": NeuralPredictor,
        "NewsSentimentTrader": NewsSentimentTrader,
        "WhaleFollower": WhaleFollower,
        "Scalper": Scalper,
    }

    for name, cls in default_tools.items():
        registry.register(AgentTool(name, cls))
    _DEFAULT_REGISTERED = True


def get_tool_signals(agent_name: str, market: Dict, balance: float) -> Dict[str, Optional[ToolResult]]:
    memory = memory_store().get_agent_memory(agent_name)
    context = ToolContext(
        agent_name=agent_name,
        market=market,
        balance=balance,
        memory=memory,
    )
    register_default_tools()
    registry = get_tool_registry()
    return registry.evaluate_all(context)
