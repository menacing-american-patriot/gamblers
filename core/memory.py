from collections import defaultdict
from typing import Any, Dict


class MemoryStore:
    def __init__(self):
        self._store: Dict[str, Dict[str, Any]] = defaultdict(dict)

    def get_agent_memory(self, agent_name: str) -> Dict[str, Any]:
        return self._store[agent_name]

    def update_agent_memory(self, agent_name: str, key: str, value: Any) -> None:
        self._store[agent_name][key] = value

    def append_agent_history(self, agent_name: str, key: str, value: Any, limit: int = 100) -> None:
        history = self._store[agent_name].setdefault(key, [])
        history.append(value)
        if len(history) > limit:
            del history[0:len(history) - limit]
