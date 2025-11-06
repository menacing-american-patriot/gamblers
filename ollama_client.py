import os
from typing import Any, Dict, List, Optional

import requests


class OllamaClient:
    def __init__(
        self,
        host: Optional[str] = None,
        model: Optional[str] = None,
        timeout: Optional[float] = None,
        api_key: Optional[str] = None,
    ):
        base_url = host or os.getenv("LLM_BASE_URL") or os.getenv("OLLAMA_HOST") or "http://localhost:11434"
        self.host = base_url.rstrip("/")
        self.model = model or os.getenv("LLM_MODEL") or os.getenv("OLLAMA_MODEL")
        if not self.model:
            raise ValueError("LLM model is required (set LLM_MODEL or OLLAMA_MODEL)")
        timeout_env = timeout if timeout is not None else os.getenv("LLM_TIMEOUT") or os.getenv("OLLAMA_TIMEOUT") or "20"
        self.timeout = float(timeout_env)
        self.api_key = api_key or os.getenv("LLM_API_KEY")
        self.temperature = os.getenv("LLM_TEMPERATURE") or os.getenv("OLLAMA_TEMPERATURE")

    def _headers(self) -> Dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    def _build_messages(self, prompt: str, system: Optional[str]) -> List[Dict[str, str]]:
        messages: List[Dict[str, str]] = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        return messages

    def generate(self, prompt: str, system: str = None, max_tokens: int = None) -> str:
        payload: Dict[str, Any] = {
            "model": self.model,
            "messages": self._build_messages(prompt, system),
        }

        if self.temperature is not None:
            payload["temperature"] = float(self.temperature)
        if max_tokens is not None:
            payload["max_tokens"] = int(max_tokens)

        response = requests.post(
            f"{self.host}/v1/chat/completions",
            json=payload,
            headers=self._headers(),
            timeout=self.timeout,
        )
        response.raise_for_status()
        data = response.json()
        choices = data.get("choices", [])
        if not choices:
            return ""
        message = choices[0].get("message", {})
        content = message.get("content", "")
        return content.strip()
