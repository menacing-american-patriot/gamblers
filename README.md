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

## 🚀 Setup

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Configure your credentials:
```bash
cp .env.example .env
```

Edit `.env` and add:
- `PRIVATE_KEY`: Your Ethereum private key (for signing transactions)
- `POLYGON_RPC_URL`: Polygon RPC endpoint (default: https://polygon-rpc.com)

3. Fund your wallet:
   - Make sure your Ethereum address has USDC on Polygon network
   - Agents work with ANY amount (default $10 each, but $1-5 works fine)
   - Total needed = (number of agents) × (amount per agent)
   - Example: 5 agents with $2 each = $10 total needed

## 🎮 Usage

Run all agents:
```bash
python run_agents.py
```

You'll be prompted for:
- Initial balance per agent (default: $10)
- Max trading iterations (default: 50)
- Sleep time between rounds (default: 30s)

The script will:
- Deploy all 5 agents in parallel
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

Good luck and may the odds be ever in your favor! 🍀
