#!/usr/bin/env python3
import argparse
import curses
import time
from typing import Dict, List

from dotenv import load_dotenv

from agents import (
    YOLOAgent,
    ValueHunter,
    MomentumChaser,
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
from core import memory_store, portfolio
from core.agent_runner import AgentRunner


AGENT_REGISTRY = {
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

DEFAULT_SELECTION = [
    "NeuralPredictor",
    "ArbitrageHunter",
    "NewsSentimentTrader",
    "WhaleFollower",
    "Scalper",
    "LlmDecisionAgent",
    "ManagerAgent",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Interactive TUI for Polymarket agents")
    parser.add_argument(
        "--agents",
        nargs="*",
        default=DEFAULT_SELECTION,
        help="Names of agents to manage (default: advanced + LLM + manager)",
    )
    parser.add_argument(
        "--balance",
        type=float,
        default=5.0,
        help="Initial balance per agent",
    )
    parser.add_argument(
        "--iterations",
        type=int,
        default=200,
        help="Maximum iterations per agent run",
    )
    parser.add_argument(
        "--sleep",
        type=int,
        default=15,
        help="Sleep interval (seconds) between iterations",
    )
    return parser.parse_args()


def build_agents(agent_names: List[str], balance: float):
    agents = []
    for name in agent_names:
        cls = AGENT_REGISTRY.get(name)
        if not cls:
            continue
        kwargs = {"initial_balance": balance}
        agents.append(cls(**kwargs))
    return agents


def draw_table(stdscr, runner: AgentRunner, agent_names: List[str], selected_idx: int):
    snapshot_store = memory_store()
    header = "{:<3} {:<20} {:<10} {:<10} {:<8} {:<10} {:<12}".format(
        "Idx", "Agent", "Status", "Balance", "P/L", "Trades", "Last Action"
    )
    stdscr.addstr(3, 2, header, curses.A_BOLD)

    for idx, name in enumerate(agent_names):
        memory = snapshot_store.snapshot(name)
        stats = (memory.get("stats") or [])[-1] if memory.get("stats") else None
        balance = stats.get("current_balance") if stats else "-"
        profit = stats.get("profit") if stats else "-"
        trades = stats.get("trades_made") if stats else "-"
        status = memory.get("status", "idle")
        last_trade = memory.get("last_trade")
        if last_trade:
            last_action = f"{last_trade.get('side')} {last_trade.get('price', 0):.2f}"
        else:
            last_action = "-"

        line = "{:<3} {:<20} {:<10} {:<10} {:<10} {:<8} {:<12}".format(
            idx,
            name,
            status,
            f"${balance:.2f}" if isinstance(balance, (int, float)) else str(balance),
            f"${profit:.2f}" if isinstance(profit, (int, float)) else str(profit),
            trades if isinstance(trades, int) else str(trades),
            last_action,
        )

        attr = curses.A_REVERSE if idx == selected_idx else curses.A_NORMAL
        stdscr.addstr(4 + idx, 2, line, attr)


def draw_footer(stdscr):
    commands = "[Up/Down] Select  [Enter/S] Start  [P] Pause  [A] Start all  [X] Stop all  [Q] Quit"
    height, width = stdscr.getmaxyx()
    stdscr.addstr(height - 2, 2, commands, curses.A_DIM)


def draw_details(stdscr, agent_name: str, y_offset: int = 20):
    memory = memory_store().snapshot(agent_name)
    stdscr.addstr(y_offset, 2, f"Details for {agent_name}", curses.A_BOLD)
    stdscr.addstr(y_offset + 1, 2, f"Status: {memory.get('status', 'unknown')}")
    stdscr.addstr(y_offset + 2, 2, f"Allocation: ${memory.get('allocation', 0):.2f}")
    positions = memory.get("positions", {})
    stdscr.addstr(y_offset + 3, 2, f"Positions: {positions if positions else '{}'}")
    last_trade = memory.get("last_trade")
    if last_trade:
        trade_str = (
            f"{last_trade.get('side')} {last_trade.get('shares', 0):.4f} @ {last_trade.get('price', 0):.4f}"
        )
        stdscr.addstr(y_offset + 4, 2, f"Last trade: {trade_str}")
    else:
        stdscr.addstr(y_offset + 4, 2, "Last trade: -")
    last_error = memory.get("last_error")
    stdscr.addstr(y_offset + 5, 2, f"Last error: {last_error or '-'}")


def run_tui(stdscr, runner: AgentRunner, agent_names: List[str]):
    curses.curs_set(0)
    stdscr.nodelay(True)
    selected_idx = 0

    while True:
        stdscr.erase()
        stdscr.addstr(1, 2, "Polymarket Agent Dashboard", curses.A_BOLD)
        portfolio_summary = portfolio().summary()
        summary_line = (
            f"Treasury: total ${portfolio_summary['total_cash']:.2f} | "
            f"allocated ${portfolio_summary['allocated_cash']:.2f} | "
            f"available ${portfolio_summary['available_cash']:.2f}"
        )
        stdscr.addstr(2, 2, summary_line, curses.A_DIM)
        draw_table(stdscr, runner, agent_names, selected_idx)
        draw_details(stdscr, agent_names[selected_idx], y_offset=6 + len(agent_names))
        draw_footer(stdscr)
        stdscr.refresh()

        try:
            key = stdscr.getch()
        except curses.error:
            key = -1

        if key == ord('q') or key == ord('Q'):
            runner.stop_all()
            break
        elif key in (curses.KEY_DOWN, ord('j')):
            selected_idx = (selected_idx + 1) % len(agent_names)
        elif key in (curses.KEY_UP, ord('k')):
            selected_idx = (selected_idx - 1) % len(agent_names)
        elif key in (curses.KEY_ENTER, 10, 13, ord('s'), ord('S')):
            runner.start_agent(agent_names[selected_idx])
        elif key in (ord('p'), ord('P')):
            runner.stop_agent(agent_names[selected_idx])
        elif key in (ord('a'), ord('A')):
            runner.start_all()
        elif key in (ord('x'), ord('X')):
            runner.stop_all()

        time.sleep(0.2)


def main():
    load_dotenv()
    args = parse_args()
    agent_names = [name for name in args.agents if name in AGENT_REGISTRY]
    if not agent_names:
        agent_names = DEFAULT_SELECTION

    agents = build_agents(agent_names, args.balance)
    runner = AgentRunner(agents, max_iterations=args.iterations, sleep_time=args.sleep)

    try:
        curses.wrapper(run_tui, runner, agent_names)
    finally:
        runner.shutdown()


if __name__ == "__main__":
    main()
