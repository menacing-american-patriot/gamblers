# 🎰 Polymarket Gambling Agents

A collection of AI agents that autonomously trade on Polymarket with different strategies. Give each agent ~$10 and watch them go wild trying to maximize profits.

## 🤖 The Agents

### Original Agents (Conservative Strategies)

1. **YOLO Agent** 🎲
   - Strategy: Maximum risk, goes all-in on gut feelings
   - Bet size: 30% of balance per trade
   - Risk level: EXTREME

2. **Value Hunter** 💎
   - Strategy: Finds mispriced markets with extreme probabilities
   - Bet size: 15% of balance per trade
   - Risk level: Medium-High

3. **Momentum Chaser** 📈
   - Strategy: Rides the wave of popular opinion
   - Bet size: 20% of balance per trade
   - Risk level: Medium

4. **Contrarian** 🔄
   - Strategy: Bets against consensus and fades the public
   - Bet size: 18% of balance per trade
   - Risk level: Medium-High

5. **Diversifier** 🎯
   - Strategy: Spreads small bets across many markets
   - Bet size: 5% of balance per trade
   - Risk level: Low-Medium

### Advanced Agents (Aggressive AI-Powered Strategies)

6. **Neural Predictor** 🧠
   - Strategy: Machine learning-inspired pattern recognition with adaptive betting
   - Uses Kelly Criterion for optimal bet sizing
   - Learns from successful patterns and adjusts strategy
   - Bet size: 25-50% (dynamic based on confidence)
   - Risk level: High

7. **Arbitrage Hunter** 💎
   - Strategy: Exploits pricing inefficiencies and logical inconsistencies
   - Finds correlated markets with mispricing
   - Detects mutually exclusive events that sum > 100%
   - Bet size: 35% base, up to 80% for high-confidence arbitrage
   - Risk level: Medium-High (but theoretically profitable)

8. **News & Sentiment Trader** 📰
   - Strategy: Rapid trades based on market sentiment shifts
   - Detects trending topics and rides sentiment waves
   - Tracks hot topics (politics, crypto, sports)
   - Bet size: 30% base, boosted for trending markets
   - Risk level: High

9. **Whale Follower** 🐋
   - Strategy: Mimics large traders and potential insider activity
   - Detects whale trades (>$50k) and unusual patterns
   - Follows smart money with aggressive positioning
   - Inspired by your Ahab whale detection tool!
   - Bet size: 40% base, up to 70% when following confirmed whales
   - Risk level: Very High

10. **Scalper** ⚡
    - Strategy: High-frequency trading on micro price movements
    - Makes many small trades for quick profits
    - Targets 3% profit per trade with 2% stop loss
    - Bet size: 15% per trade but high frequency
    - Risk level: Medium (many small bets)

11. **LLM Decision Agent** 🤖
    - Strategy: Delegates market analysis to an Ollama-hosted language model
    - Consumes market snapshots and returns JSON trading instructions
    - Configurable model, temperature, and minimum confidence thresholds
    - Bet size: Uses LLM-suggested percentage capped between 1% and 90%
    - Risk level: Depends on chosen model and prompt tuning

12. **Manager Agent** 🧭
    - Strategy: Acts as an orchestrator that queries the other strategy tools, scores their suggestions, and deploys capital to the strongest signal
    - Maintains shared memory of tool performance to adapt bet sizing and kill weak ideas
    - Bet size: 18% default (configurable) with caps based on confidence and portfolio state
    - Risk level: Medium-High (follows ensemble guidance but still aggressive)

## 🚀 Setup

1. Create and activate a virtual environment:
```bash
# Create virtual environment
python3 -m venv venv

# Activate it (Linux/Mac)
source venv/bin/activate

# Activate it (Windows)
# venv\Scripts\activate
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Configure your credentials:
```bash
cp .env.example .env
```

Edit `.env` and add:
- `PRIVATE_KEY`: Your Ethereum private key (used for signing orders)
- `POLYGON_RPC_URL`: Polygon RPC endpoint (default: https://polygon-rpc.com)
- `POLY_API_KEY`, `POLY_API_SECRET`, `POLY_API_PASSPHRASE`: Level-2 Polymarket CLOB API credentials. These are required to actually submit orders; without them the agents will remain in read-only mode. You can create/derive these keys from the Polymarket dashboard or via the official py-clob-client tooling (see [Polymarket docs](https://docs.polymarket.com/)).
- `PORTFOLIO_STARTING_CASH`: Total treasury for the shared portfolio (default 100 USDC). Each agent draws from this, and profits recycle back into the pool.

4. (Optional) Enable LLM-driven agents:
   - Install [Ollama](https://ollama.com/) locally (or point to any OpenAI-compatible endpoint)
   - Pull a model, e.g. `ollama pull llama3.1`
   - Set `LLM_BASE_URL`, `LLM_MODEL`, and optional `LLM_API_KEY`, `LLM_TIMEOUT`, `LLM_TEMPERATURE` in `.env`
   - Tune the LLM layer with `OLLAMA_BET_PCT`, `OLLAMA_MIN_CONFIDENCE`, `OLLAMA_MAX_TOKENS`
   - If you are using Ollama, leave `LLM_PROVIDER=ollama` and `LLM_FORCE_JSON=true` so the model returns strict JSON; set `LLM_FORCE_JSON=false` if your endpoint doesn’t support the `format=json` flag.
   - To enable the hive-mind coordinator, provide `HIVEMIND_COORDINATOR_MODEL` plus a comma-separated `HIVEMIND_SPECIALIST_MODELS` list; the coordinator will consult each specialist model in parallel and only execute if the committee approves.
   - Start the Ollama server (`ollama serve`) so the agent can reach your endpoint

5. Fund your wallet:
   - Make sure your Ethereum address has USDC on Polygon network
   - Agents work with ANY amount (default $10 each, but $1-5 works fine)
   - Total needed = (number of agents) × (amount per agent)
   - Example: 5 agents with $2 each = $10 total needed

## 🎮 Usage

Make sure your virtual environment is activated, then run:
```bash
# Activate virtual environment first (if not already active)
source venv/bin/activate  # Linux/Mac
# or
# venv\Scripts\activate  # Windows

# Run the agents
python run_agents.py
```

### Interactive TUI dashboard

If you prefer a real-time dashboard with start/stop controls, launch the curses-based interface:

```bash
python tui.py --balance 5 --iterations 200 --sleep 15
```

Key bindings: `↑/↓` move selection, `Enter` or `S` start selected agent, `P` pause selected, `A` start all, `X` stop all, `Q` quit. The TUI reads the shared memory store, so it reflects live balances, positions, and last trades (note: on Windows the standard `curses` module requires WSL or Python 3.8+).

### Multi-agent swarm coordinator

For a fully managed, capital-sharing swarm that ranks proposals from every strategy each round, run:

```bash
python swarm.py --balance 5 --iterations 300 --sleep 15 --markets 40 --per-agent 6
```

The swarm uses a single treasury, scores each agent’s trade proposals, executes the highest conviction plays, and records performance in the shared memory store (viewable via the TUI or logs).

You'll be prompted for:
- Initial balance per agent (default: $10)
- Max trading iterations (default: 50)
- Sleep time between rounds (default: 30s)

The script will:
- Deploy the selected agents in parallel
- Each agent trades independently with its own strategy
- Show real-time progress and final results
- Save detailed results to `results_TIMESTAMP.json`

## 📊 Monitoring

- **Console output**: Shows high-level progress for all agents
- **Agent logs**: Detailed logs in `agent_logs/` directory (one file per agent)
- **Results file**: JSON file with complete statistics after completion

## ⚠️ Disclaimer

This is for educational/entertainment purposes. Prediction markets involve real money and risk. You can lose your entire investment. Trade responsibly and only with money you can afford to lose.

Key risks:
- Agents use randomized decision-making
- Market conditions can change rapidly
- Liquidity may be limited
- Gas fees apply to all transactions
- No guarantee of profit

## 🛠️ Customization

Want to create your own agent? Extend the `BaseAgent` class:

```python
from base_agent import BaseAgent

class MyAgent(BaseAgent):
    def analyze_market(self, market):
        # Your strategy logic here
        return {
            "token_id": "...",
            "side": "BUY" or "SELL",
            "amount": bet_amount,
            "price": target_price
        }
    
    def should_continue(self):
        # Your stopping condition
        return self.current_balance > 1.0
```

Add it to `agents/__init__.py` and include it in `run_agents.py`.

## 📝 Notes

- Agents run independently and concurrently
- Each agent tracks its own balance and trades
- Agents stop when they hit minimum balance or max iterations
- All transactions are logged for audit purposes
- Results are saved with timestamp for tracking performance over time
- If the Polymarket API credentials are missing or invalid, the agents will log a warning and skip order placement while still evaluating markets.
- The LLM Decision Agent and Manager Agent use the shared tool framework; they require a reachable LLM endpoint and will fall back gracefully if `LLM_MODEL` is unset.
- A shared memory store keeps track of balances, positions, and tool scores so orchestrators can avoid selling unowned shares and adapt to past performance.
- The TUI (`tui.py`) can monitor and control agents in real time; it relies on the same memory store and runner services used by the CLI.
- The swarm coordinator (`swarm.py`) manages a shared treasury, ranks strategy proposals, and seeks to maximize profit across the entire portfolio rather than per-agent silos.
- Every strategy now routes its heuristic proposal through the LLM manager (when configured), allowing the model to approve, tweak, or veto trades before they hit the CLOB.
- Setting `HIVEMIND_COORDINATOR_MODEL` and `HIVEMIND_SPECIALIST_MODELS` activates a multi-model hive mind: fast specialists produce draft trades, a coordinator model arbitrates, and the final order is executed only if the consensus passes risk checks.

Good luck and may the odds be ever in your favor! 🍀
