#!/usr/bin/env python3
import argparse
import time

from dotenv import load_dotenv

from agents import (
    MomentumChaser,
    ValueHunter,
    YOLOAgent,
    Contrarian,
    Diversifier,
    NeuralPredictor,
    ArbitrageHunter,
    NewsSentimentTrader,
    WhaleFollower,
    Scalper,
    LlmDecisionAgent,
    ManagerAgent,
)
from core import market_data_service, memory_store


STRATEGY_REGISTRY = {
    "YOLOAgent": YOLOAgent,
    "ValueHunter": ValueHunter,
    "MomentumChaser": MomentumChaser,
    "Contrarian": Contrarian,
    "Diversifier": Diversifier,
    "NeuralPredictor": NeuralPredictor,
    "ArbitrageHunter": ArbitrageHunter,
    "NewsSentimentTrader": NewsSentimentTrader,
    "WhaleFollower": WhaleFollower,
    "Scalper": Scalper,
    "LlmDecisionAgent": LlmDecisionAgent,
    "ManagerAgent": ManagerAgent,
}

DEFAULT_STRATEGIES = [
    "NeuralPredictor",
    "ArbitrageHunter",
    "NewsSentimentTrader",
    "WhaleFollower",
    "Scalper",
    "LlmDecisionAgent",
    "ManagerAgent",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Multi-agent swarm coordinator for Polymarket trading")
    parser.add_argument(
        "--agents",
        nargs="*",
        default=DEFAULT_STRATEGIES,
        help="Agent names to include in the swarm",
    )
    parser.add_argument("--balance", type=float, default=5.0, help="Requested allocation per agent")
    parser.add_argument("--iterations", type=int, default=200, help="Number of swarm iterations")
    parser.add_argument("--sleep", type=int, default=15, help="Seconds to wait between rounds")
    parser.add_argument("--markets", type=int, default=25, help="How many markets to scan per round")
    parser.add_argument("--per-agent", type=int, default=5, help="Markets per agent per round")
    return parser.parse_args()


def build_agents(names, balance):
    instances = []
    for name in names:
        cls = STRATEGY_REGISTRY.get(name)
        if not cls:
            continue
        instances.append(cls(initial_balance=balance))
    return instances


def analyze_agents(agents, markets, markets_per_agent):
    proposals = []
    for agent in agents:
        agent_memory = memory_store().get_agent_memory(agent.name)
        agent_memory["status"] = "evaluating"
        agent.current_balance = agent.portfolio.get_agent_balance(agent.name)
        count = 0
        for market in markets:
            if count >= markets_per_agent:
                break
            if not agent.should_continue():
                agent_memory["status"] = "stopped"
                break
            decision = agent.analyze_market(market)
            if decision:
                proposals.append((agent, market, decision))
            count += 1
    return proposals


def execute_proposals(proposals):
    # Sort proposals by proposed dollar amount descending
    proposals.sort(key=lambda item: item[2].get("amount", 0.0), reverse=True)
    executed = 0
    for agent, market, decision in proposals:
        side = decision.get("side")
        token_id = decision.get("token_id")
        amount = decision.get("amount")
        price = decision.get("price") or market.get("price")
        if not all([side, token_id, amount, price]):
            continue
        if agent.place_bet(token_id, side, amount, price):
            executed += 1
            memory = memory_store().get_agent_memory(agent.name)
            memory["status"] = "trading"
    return executed


def swarm_loop(agents, *, max_iterations: int, sleep_time: int, markets_limit: int, markets_per_agent: int):
    mds = market_data_service()
    for iteration in range(max_iterations):
        markets = mds.get_active_markets(limit=markets_limit)
        if not markets:
            time.sleep(sleep_time)
            continue
        proposals = analyze_agents(agents, markets, markets_per_agent)
        executed = execute_proposals(proposals)
        for agent in agents:
            memory_store().get_agent_memory(agent.name)["status"] = "idle"
            agent.log_stats()
        time.sleep(sleep_time)
        if executed == 0:
            # If nobody traded, wait a little extra to avoid hammering the API
            time.sleep(1)


def main():
    load_dotenv()
    args = parse_args()
    agent_names = [name for name in args.agents if name in STRATEGY_REGISTRY]
    if not agent_names:
        agent_names = DEFAULT_STRATEGIES
    agents = build_agents(agent_names, args.balance)
    try:
        swarm_loop(
            agents,
            max_iterations=args.iterations,
            sleep_time=args.sleep,
            markets_limit=args.markets,
            markets_per_agent=args.per_agent,
        )
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
