#!/usr/bin/env python3
import os
import sys
from dotenv import load_dotenv
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
from datetime import datetime

from agents import (
    YOLOAgent, ValueHunter, MomentumChaser, Contrarian, Diversifier,
    NeuralPredictor, ArbitrageHunter, NewsSentimentTrader, 
    WhaleFollower, Scalper
)

def run_single_agent(agent, max_iterations=50, sleep_time=30):
    """Run a single agent and return its stats"""
    try:
        stats = agent.run(max_iterations=max_iterations, sleep_time=sleep_time)
        return stats
    except Exception as e:
        print(f"Error running {agent.name}: {e}")
        return agent.get_stats()

def main():
    load_dotenv()
    
    if not os.getenv("PRIVATE_KEY"):
        print("❌ Error: PRIVATE_KEY not found in .env file")
        print("Please copy .env.example to .env and fill in your credentials")
        sys.exit(1)
    
    print("=" * 80)
    print("🎰 POLYMARKET GAMBLING AGENTS 🎰")
    print("=" * 80)
    print()
    
    initial_balance = float(input("Enter initial balance per agent (default $10): ") or "10")
    max_iterations = int(input("Enter max trading iterations (default 50): ") or "50")
    sleep_time = int(input("Enter sleep time between rounds in seconds (default 30): ") or "30")
    
    print()
    print("Select agents to deploy:")
    print("1. Original 5 agents (YOLO, Value, Momentum, Contrarian, Diversifier)")
    print("2. New Advanced 5 agents (Neural, Arbitrage, Sentiment, Whale, Scalper)")
    print("3. All 10 agents (Warning: Resource intensive!)")
    print("4. Custom selection")
    
    choice = input("Enter choice (1-4, default 2): ") or "2"
    
    if choice == "1":
        agents = [
            YOLOAgent(initial_balance),
            ValueHunter(initial_balance),
            MomentumChaser(initial_balance),
            Contrarian(initial_balance),
            Diversifier(initial_balance)
        ]
    elif choice == "2":
        agents = [
            NeuralPredictor(initial_balance=initial_balance),
            ArbitrageHunter(initial_balance=initial_balance),
            NewsSentimentTrader(initial_balance=initial_balance),
            WhaleFollower(initial_balance=initial_balance),
            Scalper(initial_balance=initial_balance)
        ]
    elif choice == "3":
        agents = [
            YOLOAgent(initial_balance),
            ValueHunter(initial_balance),
            MomentumChaser(initial_balance),
            Contrarian(initial_balance),
            Diversifier(initial_balance),
            NeuralPredictor(initial_balance=initial_balance),
            ArbitrageHunter(initial_balance=initial_balance),
            NewsSentimentTrader(initial_balance=initial_balance),
            WhaleFollower(initial_balance=initial_balance),
            Scalper(initial_balance=initial_balance)
        ]
    else:
        print("\nAvailable agents:")
        available = [
            ("1", "YOLOAgent", YOLOAgent),
            ("2", "ValueHunter", ValueHunter),
            ("3", "MomentumChaser", MomentumChaser),
            ("4", "Contrarian", Contrarian),
            ("5", "Diversifier", Diversifier),
            ("6", "NeuralPredictor", NeuralPredictor),
            ("7", "ArbitrageHunter", ArbitrageHunter),
            ("8", "NewsSentimentTrader", NewsSentimentTrader),
            ("9", "WhaleFollower", WhaleFollower),
            ("10", "Scalper", Scalper)
        ]
        
        for num, name, _ in available:
            print(f"  {num}. {name}")
        
        selections = input("Enter agent numbers separated by commas (e.g., 1,6,9): ").split(',')
        agents = []
        
        for sel in selections:
            sel = sel.strip()
            for num, name, agent_class in available:
                if num == sel:
                    if agent_class in [NeuralPredictor, ArbitrageHunter, NewsSentimentTrader, WhaleFollower, Scalper]:
                        agents.append(agent_class(initial_balance=initial_balance))
                    else:
                        agents.append(agent_class(initial_balance))
                    break
    
    print()
    print(f"💰 Deploying {len(agents)} agents with ${initial_balance:.2f} each...")
    print(f"🔄 Running {max_iterations} iterations with {sleep_time}s sleep time")
    print()
    
    print("🚀 Agents deployed:")
    for agent in agents:
        print(f"   • {agent.name}")
    print()
    print("⏳ Trading in progress... (check agent_logs/ for detailed logs)")
    print()
    
    all_stats = []
    
    with ThreadPoolExecutor(max_workers=min(len(agents), 10)) as executor:
        future_to_agent = {
            executor.submit(run_single_agent, agent, max_iterations, sleep_time): agent 
            for agent in agents
        }
        
        for future in as_completed(future_to_agent):
            agent = future_to_agent[future]
            try:
                stats = future.result()
                all_stats.append(stats)
                print(f"✅ {agent.name} completed")
            except Exception as e:
                print(f"❌ {agent.name} failed: {e}")
    
    print()
    print("=" * 80)
    print("📊 FINAL RESULTS")
    print("=" * 80)
    print()
    
    total_initial = sum(s['initial_balance'] for s in all_stats)
    total_final = sum(s['current_balance'] for s in all_stats)
    total_profit = total_final - total_initial
    total_roi = (total_profit / total_initial * 100) if total_initial > 0 else 0
    
    all_stats.sort(key=lambda x: x['profit'], reverse=True)
    
    for stats in all_stats:
        profit_emoji = "📈" if stats['profit'] > 0 else "📉" if stats['profit'] < 0 else "➖"
        print(f"{profit_emoji} {stats['name']:<20} | "
              f"Balance: ${stats['current_balance']:>7.2f} | "
              f"P/L: ${stats['profit']:>7.2f} ({stats['roi']:>6.1f}%) | "
              f"Trades: {stats['trades_made']:>3}")
    
    print()
    print("-" * 80)
    print(f"{'TOTAL PORTFOLIO':<20} | "
          f"Balance: ${total_final:>7.2f} | "
          f"P/L: ${total_profit:>7.2f} ({total_roi:>6.1f}%)")
    print("-" * 80)
    
    results_file = f"results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(results_file, 'w') as f:
        json.dump({
            'timestamp': datetime.now().isoformat(),
            'total_initial': total_initial,
            'total_final': total_final,
            'total_profit': total_profit,
            'total_roi': total_roi,
            'agents': all_stats
        }, f, indent=2)
    
    print()
    print(f"💾 Results saved to {results_file}")
    print()
    
    if total_profit > 0:
        print(f"🎉 Congratulations! You made ${total_profit:.2f}!")
    elif total_profit < 0:
        print(f"💸 Better luck next time! Lost ${abs(total_profit):.2f}")
    else:
        print("🤷 Broke even!")

if __name__ == "__main__":
    main()
