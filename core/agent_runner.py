from __future__ import annotations

import threading
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, List, Optional, Type

from base_agent import BaseAgent


class AgentRunner:
    def __init__(self, agents: List[BaseAgent], *, max_iterations: int = 100, sleep_time: int = 30):
        self.agents = {agent.name: agent for agent in agents}
        self.max_iterations = max_iterations
        self.sleep_time = sleep_time
        self._executor = ThreadPoolExecutor(max_workers=len(self.agents) or 1)
        self._futures: Dict[str, threading.Event] = {}

    def start_agent(self, name: str):
        agent = self.agents.get(name)
        if not agent:
            return
        if name in self._futures and not self._futures[name].is_set():
            return

        stop_event = threading.Event()
        self._futures[name] = stop_event

        def _run_agent():
            try:
                agent.run(max_iterations=self.max_iterations, sleep_time=self.sleep_time)
            finally:
                stop_event.set()

        self._executor.submit(_run_agent)

    def stop_agent(self, name: str):
        agent = self.agents.get(name)
        if not agent:
            return
        agent.request_stop()

    def start_all(self):
        for name in self.agents:
            self.start_agent(name)

    def stop_all(self):
        for name, agent in self.agents.items():
            agent.request_stop()

    def is_running(self, name: str) -> bool:
        event = self._futures.get(name)
        if not event:
            return False
        return not event.is_set()

    def get_agent_names(self) -> List[str]:
        return list(self.agents.keys())

    def shutdown(self):
        self.stop_all()
        self._executor.shutdown(wait=False)
