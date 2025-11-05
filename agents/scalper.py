"""
High-Frequency Scalper - Makes rapid small trades to exploit micro price movements
Targets quick profits through volume rather than large bets
"""
from typing import Dict, Optional, List
from base_agent import BaseAgent
import random
from collections import deque

class Scalper(BaseAgent):
    def __init__(self, name: str = "Scalper", initial_balance: float = 10.0):
        super().__init__(name, initial_balance)
        self.price_history = {}  # Track micro movements
        self.trade_queue = deque(maxlen=20)  # Recent trades
        self.base_bet_percentage = 0.15  # Smaller bets, more frequent
        self.profit_target = 0.03  # 3% profit target per trade
        self.stop_loss = 0.02  # 2% stop loss
        self.momentum_trades = 0
        self.reversal_trades = 0
        
    def _detect_micro_pattern(self, prices: List[float]) -> str:
        """Detect micro price patterns for scalping"""
        if len(prices) < 3:
            return 'unknown'
        
        # Calculate micro movements
        changes = [prices[i] - prices[i-1] for i in range(1, len(prices))]
        
        # Patterns
        if all(c > 0 for c in changes[-2:]):  # Rising
            return 'momentum_up'
        elif all(c < 0 for c in changes[-2:]):  # Falling
            return 'momentum_down'
        elif len(changes) >= 3:
            # Reversal patterns
            if changes[-3] > 0 and changes[-2] > 0 and changes[-1] < 0:
                return 'reversal_down'
            elif changes[-3] < 0 and changes[-2] < 0 and changes[-1] > 0:
                return 'reversal_up'
        
        # Volatility check
        if prices[-1] > max(prices[:-1]) * 1.01:  # 1% above recent high
            return 'breakout_up'
        elif prices[-1] < min(prices[:-1]) * 0.99:  # 1% below recent low
            return 'breakout_down'
        
        return 'ranging'
    
    def _calculate_spread_opportunity(self, price: float) -> float:
        """Calculate potential profit from spread"""
        # Best opportunities at extreme prices (wider spreads)
        if price < 0.1 or price > 0.9:
            return 0.05  # 5% potential
        elif price < 0.2 or price > 0.8:
            return 0.03  # 3% potential
        elif price < 0.3 or price > 0.7:
            return 0.02  # 2% potential
        else:
            return 0.01  # 1% potential in middle prices
    
    def _should_scalp(self, pattern: str, price: float, spread_opp: float) -> Tuple[bool, str, float]:
        """Determine if we should make a scalp trade"""
        
        # Momentum scalping
        if pattern == 'momentum_up' and price < 0.85:
            return True, 'BUY', 0.7  # Follow momentum
        elif pattern == 'momentum_down' and price > 0.15:
            return True, 'SELL', 0.7
        
        # Reversal scalping
        elif pattern == 'reversal_up' and price < 0.7:
            return True, 'BUY', 0.6
        elif pattern == 'reversal_down' and price > 0.3:
            return True, 'SELL', 0.6
        
        # Breakout scalping
        elif pattern == 'breakout_up' and price < 0.8:
            return True, 'BUY', 0.75
        elif pattern == 'breakout_down' and price > 0.2:
            return True, 'SELL', 0.75
        
        # Range trading
        elif pattern == 'ranging':
            if price < 0.4:
                return True, 'BUY', 0.5  # Buy low in range
            elif price > 0.6:
                return True, 'SELL', 0.5  # Sell high in range
        
        # Spread arbitrage at extremes
        if spread_opp >= 0.03:  # 3%+ opportunity
            if price < 0.2:
                return True, 'BUY', 0.8
            elif price > 0.8:
                return True, 'SELL', 0.8
        
        return False, '', 0
    
    def _quick_exit_check(self) -> bool:
        """Check if we should exit recent positions"""
        if len(self.trade_queue) == 0:
            return False
        
        recent_trades = list(self.trade_queue)[-5:]
        
        # If last 3 trades were losses, pause
        if len(recent_trades) >= 3:
            last_three = recent_trades[-3:]
            if all(t.get('result', 'unknown') == 'loss' for t in last_three):
                return True
        
        return False
    
    def analyze_market(self, market: Dict) -> Optional[Dict]:
        try:
            token_id = market.get('token_id')
            if not token_id:
                return None
            
            price = self.get_market_price(token_id)
            if not price:
                return None
            
            # Initialize or update price history
            if token_id not in self.price_history:
                self.price_history[token_id] = deque(maxlen=10)
            
            self.price_history[token_id].append(price)
            prices = list(self.price_history[token_id])
            
            # Need at least 3 prices for pattern detection
            if len(prices) < 3:
                return None
            
            # Check if we should pause
            if self._quick_exit_check():
                self.logger.info("⏸️ Pausing after losses")
                return None
            
            # Detect pattern
            pattern = self._detect_micro_pattern(prices)
            
            # Calculate spread opportunity
            spread_opp = self._calculate_spread_opportunity(price)
            
            # Decide if we should scalp
            should_trade, side, confidence = self._should_scalp(pattern, price, spread_opp)
            
            if not should_trade:
                return None
            
            # Filter for high-activity markets (better for scalping)
            volume = market.get('volume', 0)
            liquidity = market.get('liquidity', 0)
            
            if volume < 10000 or liquidity < 5000:
                return None  # Skip low activity markets
            
            # Calculate position size
            base_bet = self.base_bet_percentage
            
            # Adjust for confidence
            bet_percentage = base_bet * confidence
            
            # Boost for high liquidity (easier to exit)
            if liquidity > 50000:
                bet_percentage *= 1.3
            elif liquidity > 20000:
                bet_percentage *= 1.15
            
            # Reduce size if we've had recent losses
            recent_losses = sum(1 for t in self.trade_queue if t.get('result') == 'loss')
            if recent_losses > 2:
                bet_percentage *= 0.7
            
            # Quick trades = smaller sizes but more frequent
            amount = min(
                self.current_balance * bet_percentage,
                self.current_balance * 0.3  # Max 30% per scalp
            )
            
            # Track the trade
            trade_info = {
                'token_id': token_id,
                'side': side,
                'price': price,
                'pattern': pattern,
                'amount': amount,
                'timestamp': datetime.now()
            }
            self.trade_queue.append(trade_info)
            
            # Log scalping action
            self.logger.info(f"⚡ SCALP: {pattern} | {side} @ {price:.3f} | "
                           f"Spread opp: {spread_opp:.1%} | "
                           f"Size: ${amount:.2f}")
            
            # Track pattern usage
            if 'momentum' in pattern:
                self.momentum_trades += 1
            elif 'reversal' in pattern:
                self.reversal_trades += 1
            
            return {
                "token_id": token_id,
                "side": side,
                "amount": amount,
                "price": price
            }
            
        except Exception as e:
            self.logger.error(f"Scalping error: {e}")
            return None
    
    def should_continue(self) -> bool:
        # Continue until 5% of initial (scalpers can recover)
        if self.current_balance < self.initial_balance * 0.05:
            return False
        
        # Adapt strategy based on performance
        if len(self.trade_queue) >= 10:
            recent_trades = list(self.trade_queue)[-10:]
            wins = sum(1 for t in recent_trades if t.get('result') == 'win')
            
            if wins > 7:  # 70%+ win rate
                self.base_bet_percentage = min(self.base_bet_percentage * 1.2, 0.25)
                self.logger.info("📈 Increasing scalp size due to high win rate")
            elif wins < 3:  # Under 30% win rate
                self.base_bet_percentage = max(self.base_bet_percentage * 0.8, 0.05)
                self.logger.info("📉 Decreasing scalp size due to low win rate")
        
        # Log pattern performance periodically
        if (self.momentum_trades + self.reversal_trades) % 20 == 0 and \
           (self.momentum_trades + self.reversal_trades) > 0:
            self.logger.info(f"📊 Pattern stats - Momentum: {self.momentum_trades}, "
                           f"Reversal: {self.reversal_trades}")
        
        return True

from typing import Tuple
from datetime import datetime
