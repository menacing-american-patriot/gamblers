import json
import logging
import os
from typing import Dict, List, Optional

from ollama_client import OllamaClient


FALLBACK_FLAG = "__hivemind_fallback__"


class HivemindCoordinator:
    def __init__(self):
        specialist_env = os.getenv("HIVEMIND_SPECIALIST_MODELS", "")
        self.specialist_models: List[str] = [m.strip() for m in specialist_env.split(",") if m.strip()]
        self.coordinator_model = os.getenv("HIVEMIND_COORDINATOR_MODEL")
        self.max_tokens = int(os.getenv("HIVEMIND_MAX_TOKENS", "384"))
        self.force_json = os.getenv("HIVEMIND_FORCE_JSON", os.getenv("LLM_FORCE_JSON", "true")).lower() in {"1", "true", "yes"}

        self.logger = logging.getLogger("Hivemind")
        self.enabled = bool(self.coordinator_model and self.specialist_models)
        self.client: Optional[OllamaClient] = None

        if self.enabled:
            base_model = self.coordinator_model or (self.specialist_models[0] if self.specialist_models else None)
            try:
                self.client = OllamaClient(model=base_model)
            except Exception as exc:
                self.logger.error(f"Failed to initialize Hivemind client: {exc}")
                self.enabled = False

    def _call_model(self, model: str, system_prompt: str, prompt: str) -> Optional[str]:
        if not self.client:
            return None
        try:
            return self.client.generate(
                prompt,
                system=system_prompt,
                max_tokens=self.max_tokens,
                model_override=model,
            )
        except Exception as exc:
            self.logger.error(f"LLM model '{model}' call failed: {exc}")
            return None

    def _parse_json(self, response: Optional[str]) -> Optional[Dict]:
        if not response:
            return None
        response = response.strip()
        if response.startswith("```"):
            # Remove Markdown fences like ```json ... ```
            lines = [line for line in response.splitlines() if not line.strip().startswith("```")]
            response = "\n".join(lines).strip()
        try:
            start = response.find("{")
            end = response.rfind("}")
            if start == -1 or end == -1:
                if self.force_json:
                    raise ValueError("No JSON envelope")
                self.logger.debug("Hivemind received non-JSON response; ignoring")
                return None
            return json.loads(response[start : end + 1])
        except Exception as exc:
            if self.force_json:
                self.logger.error(f"Failed to parse JSON response: {exc}. Raw: {response[:120]}...")
            else:
                self.logger.debug(f"Hivemind tolerant parse failure: {exc}")
            return None

    def collaborative_decision(
        self,
        agent_name: str,
        market: Dict,
        proposal: Dict,
        context: Dict,
    ) -> Optional[Dict]:
        if not self.enabled:
            return None

        token_id = proposal.get("token_id")
        positions = context.get("positions", {})
        available_shares = positions.get(token_id, 0.0) if token_id else 0.0

        specialist_reports: List[Dict] = []
        specialist_prompt_template = (
            "You are a specialist model assisting a trading agent. Review the base proposal and return JSON with "
            "fields action (EXECUTE or SKIP), side, amount_multiplier (float), price (optional), confidence (0-1), reasoning."
        )

        specialist_payload = {
            "agent": agent_name,
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
            "proposal": proposal,
            "portfolio_balance": context.get("balance"),
            "available_shares": available_shares,
        }

        for model in self.specialist_models:
            raw = self._call_model(
                model,
                specialist_prompt_template,
                json.dumps(specialist_payload, ensure_ascii=False),
            )
            data = self._parse_json(raw)
            if not data:
                continue
            specialist_reports.append({
                "model": model,
                "action": str(data.get("action", "")).upper(),
                "side": data.get("side"),
                "amount_multiplier": data.get("amount_multiplier"),
                "price": data.get("price"),
                "confidence": data.get("confidence"),
                "reasoning": data.get("reasoning"),
            })

        coordinator_prompt = (
            "You are the coordinator for multiple specialist models. Review their outputs and decide the final action. "
            "Return JSON with fields action (EXECUTE or SKIP), side, amount, price, reasoning. Never approve a SELL when available_shares <= 0."
        )

        coordinator_payload = {
            "agent": agent_name,
            "proposal": proposal,
            "available_shares": available_shares,
            "portfolio_balance": context.get("balance"),
            "specialists": specialist_reports,
            "market": specialist_payload["market"],
        }

        raw = self._call_model(
            self.coordinator_model,
            coordinator_prompt,
            json.dumps(coordinator_payload, ensure_ascii=False),
        )
        decision = self._parse_json(raw)
        if not decision:
            return {FALLBACK_FLAG: True}

        action = str(decision.get("action", "")).upper()
        if action != "EXECUTE":
            self.logger.info(
                f"Hivemind vetoed proposal for agent {agent_name} (action={action})"
            )
            return None

        final = dict(proposal)
        if "side" in decision and decision["side"]:
            final["side"] = str(decision["side"]).upper()
        if "price" in decision and decision["price"] is not None:
            try:
                final["price"] = float(decision["price"])
            except (TypeError, ValueError):
                pass
        if "amount" in decision and decision["amount"] is not None:
            try:
                final["amount"] = max(0.0, float(decision["amount"]))
            except (TypeError, ValueError):
                pass

        reasoning = decision.get("reasoning")
        if reasoning:
            self.logger.info(f"Hivemind reasoning ({agent_name}): {reasoning}")

        return final


_hivemind_instance: Optional[HivemindCoordinator] = None


def get_hivemind() -> HivemindCoordinator:
    global _hivemind_instance
    if _hivemind_instance is None:
        _hivemind_instance = HivemindCoordinator()
    return _hivemind_instance
