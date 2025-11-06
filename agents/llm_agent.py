import json
import os
from typing import Dict, Optional

from base_agent import BaseAgent
from core.tools import ToolResult, get_tool_signals


class LlmDecisionAgent(BaseAgent):
    def __init__(self, initial_balance: float = 10.0, name: str = None, register_with_portfolio: bool = True):
        agent_name = name or os.getenv("OLLAMA_AGENT_NAME", "LLM_Trader")
        super().__init__(agent_name, initial_balance, register_with_portfolio=register_with_portfolio)
        self.min_confidence = float(os.getenv("OLLAMA_MIN_CONFIDENCE", "0.55"))
        self.default_bet_pct = float(os.getenv("OLLAMA_BET_PCT", "0.25"))
        self.max_tokens = int(float(os.getenv("OLLAMA_MAX_TOKENS", "256")))
        self._last_tool_outputs: Dict[str, Optional[ToolResult]] = {}

    def analyze_market(self, market: Dict) -> Optional[Dict]:
        client = self.get_ollama_client()
        if not client:
            return None
        tool_signals = self._gather_tool_signals(market)
        prompt = self._build_prompt(market, tool_signals)
        try:
            response_text = client.generate(
                prompt,
                system=self._system_prompt(),
                max_tokens=self.max_tokens,
            )
        except Exception as exc:
            self.logger.error(f"Ollama request failed: {exc}")
            return None
        decision = self._parse_decision(response_text, market, tool_signals)
        if not decision:
            return None
        confidence = decision.get("confidence", 0.0)
        if confidence < self.min_confidence:
            return None
        bet_pct = decision.get("bet_pct", self.default_bet_pct)
        bet_pct = max(0.01, min(bet_pct, 0.9))
        amount = min(self.current_balance * bet_pct, self.current_balance * 0.95)
        side = decision.get("side")
        price = decision.get("price") or market.get("price")
        token_id = market.get("token_id")
        if not token_id or not side or price is None or amount <= 0:
            return None
        self.logger.info(
            f"🤖 LLM decision on {market.get('question', '')[:48]}... side={side} confidence={confidence:.2f}"
        )
        proposal = {
            "token_id": token_id,
            "side": side,
            "amount": amount,
            "price": float(price),
        }
        return self.manage_with_llm(market, proposal, "LLM Strategy")

    def should_continue(self) -> bool:
        return self.current_balance > self.initial_balance * 0.05

    def _system_prompt(self) -> str:
        return (
            "You evaluate prediction markets and decide whether to BUY (enter trading position) on an outcome "
            "or SELL (exit your position). You must buy to enter a position before you can sell to exit that same position. You have access to several strategy tools whose latest suggestions are provided. "
            "Respond with compact JSON containing fields side, confidence, bet_pct, price, reasoning, and optionally tool "
            "(set tool to the strategy name if you want to follow that tool's recommendation)."
        )

    def _build_prompt(self, market: Dict, tool_signals: Dict[str, Optional[ToolResult]]) -> str:
        info = {
            "question": market.get("question"),
            "outcome": market.get("outcome"),
            "price": market.get("price"),
            "best_bid": market.get("best_bid"),
            "best_ask": market.get("best_ask"),
            "volume": market.get("volume"),
            "liquidity": market.get("liquidity"),
            "end_date": market.get("end_date_iso"),
            "category": market.get("category"),
        }
        description = market.get("description") or market.get("longDescription")
        tool_payload = {}
        for name, decision in tool_signals.items():
            if not decision:
                tool_payload[name] = None
            else:
                tool_payload[name] = {
                    "side": decision.side,
                    "confidence": decision.confidence,
                    "price": decision.price,
                    "bet_pct": decision.bet_pct,
                    "reasoning": decision.reasoning,
                }
        positions = self.memory_store.get_agent_memory(self.name).get("positions", {})
        payload = {
            "market": info,
            "instructions": {
                "side": "BUY or SELL",
                "outcome": "Outcome being traded on",
                "confidence_range": "0.0-1.0",
                "bet_pct_hint": self.default_bet_pct,
            },
            "notes": description[:500] if description else None,
            "tools": tool_payload,
            "portfolio": {
                "positions": positions,
                "balance": self.current_balance,
            },
        }
        data_json = json.dumps(payload, ensure_ascii=False)
        return (
            "Analyze the market data and reply with JSON. Example: "
            '{"side":"BUY","outcome":"YES","confidence":0.72,"bet_pct":0.3,"price":0.41,"reasoning":"...","tool":"MomentumChaser"}'
            f"\nDATA:\n{data_json}"
        )

    def _parse_decision(self, text: str, market: Dict, tool_signals: Dict[str, Optional[ToolResult]]) -> Optional[Dict]:
        try:
            candidate = text.strip()
            if not candidate:
                return None
            # isolate JSON if wrapped in text
            start = candidate.find("{")
            end = candidate.rfind("}")
            if start == -1 or end == -1:
                return None
            parsed = json.loads(candidate[start:end + 1])
        except json.JSONDecodeError as exc:
            self.logger.error(f"Failed to parse LLM JSON: {exc}. Raw: {text[:120]}...")
            return None
        chosen_tool = parsed.get("tool")
        tool_choice = str(chosen_tool) if chosen_tool else None
        tool_decision = None
        if tool_choice and tool_choice in tool_signals:
            tool_decision = tool_signals.get(tool_choice)

        side = str(parsed.get("side", "")).upper()
        if tool_decision and not side:
            side = str(tool_decision.get("side", "")).upper()
        if side not in {"BUY", "SELL"}:
            return None
        confidence = float(parsed.get("confidence", 0))
        bet_pct = parsed.get("bet_pct")
        price = parsed.get("price")
        if tool_decision and price is None:
            price = tool_decision.price
        decision = {
            "side": side,
            "confidence": confidence,
            "bet_pct": float(bet_pct) if bet_pct is not None else None,
            "price": float(price) if price is not None else None,
        }
        if tool_decision:
            decision["tool"] = tool_choice
        reasoning = parsed.get("reasoning")
        if reasoning:
            self.logger.info(f"LLM reasoning: {reasoning[:140]}")
        return decision

    def _gather_tool_signals(self, market: Dict) -> Dict[str, Optional[ToolResult]]:
        signals = get_tool_signals(self.name, market, self.current_balance)
        self._last_tool_outputs = signals
        return signals
