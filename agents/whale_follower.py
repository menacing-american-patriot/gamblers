"""
Whale Follower - Follows large trades and potential insider activity
Mimics smart money movements and whale patterns
"""
from typing import Dict, Optional, List, Tuple
from base_agent import BaseAgent
from datetime import datetime, timedelta
import random

class WhaleFollower(BaseAgent):
    def __init__(self, name: str = "WhaleFollower", initial_balance: float = 10.0):
        super().__init__(name, initial_balance)
        self.whale_trades = {}  # Track large trades per market
        self.whale_threshold = 50000  # $50k+ considered whale
        self.insider_indicators = {}  # Track suspicious patterns
        self.base_bet_percentage = 0.4  # Aggressive when following whales
        self.confidence_multiplier = 1.0
        
    def _detect_whale_activity(self, market: Dict) -> Tuple[bool, Dict]:
        """
        Detect whale activity based on market metrics
        Returns (is_whale_active, whale_info)
        """
        volume = market.get('volume', 0)
        liquidity = market.get('liquidity', 0)
        num_traders = market.get('num_traders', 0)
        
        # Indicators of whale activity
        whale_score = 0
        whale_info = {
            'volume': volume,
            'liquidity': liquidity,
            'num_traders': num_traders,
            'concentration': 0,
            'sudden_spike': False,
            'low_trader_high_volume': False
        }
        
        # High volume with low number of traders = concentration
        if num_traders > 0:
            avg_trade_size = volume / num_traders
            if avg_trade_size > 5000:  # $5k+ average
                whale_score += 3
                whale_info['concentration'] = avg_trade_size
                whale_info['low_trader_high_volume'] = True
        
        # Volume spike detection
        token_id = market.get('token_id')
        if token_id and token_id in self.whale_trades:
            prev_volume = self.whale_trades[token_id].get('last_volume', 0)
            if volume > prev_volume * 2 and volume > 100000:
                whale_score += 2
                whale_info['sudden_spike'] = True
        
        # High volume relative to liquidity (market impact)
        if liquidity > 0:
            impact_ratio = volume / liquidity
            if impact_ratio > 5:  # Volume 5x liquidity
                whale_score += 2
        
        # Absolute volume threshold
        if volume > 500000:
            whale_score += 3
        elif volume > 200000:
            whale_score += 2
        elif volume > 100000:
            whale_score += 1
        
        is_whale = whale_score >= 4
        whale_info['score'] = whale_score
        
        return is_whale, whale_info
    
    def _detect_insider_patterns(self, market: Dict, whale_info: Dict) -> float:
        """
        Detect potential insider trading patterns
        Returns confidence score (0-1)
        """
        confidence = 0.0
        
        # Pattern 1: Low liquidity, high volume (like Ahab detects)
        if whale_info['liquidity'] > 0:
            impact = whale_info['volume'] / whale_info['liquidity']
            if impact > 2:  # 200% impact
                confidence += 0.3
            if impact > 5:  # 500% impact
                confidence += 0.2
        
        # Pattern 2: Few traders but huge volume
        if whale_info['low_trader_high_volume']:
            confidence += 0.25
        
        # Pattern 3: Sudden spike in otherwise quiet market
        if whale_info['sudden_spike']:
            confidence += 0.2
        
        # Pattern 4: Check for timing patterns (near events)
        question = market.get('question', '').lower()
        if any(word in question for word in ['tonight', 'today', 'tomorrow', 'hours']):
            # Close to event = potential insider knowledge
            confidence += 0.15
        
        # Pattern 5: Extreme price movements
        token_id = market.get('token_id')
        current_price = self.get_market_price(token_id)
        if current_price:
            if current_price < 0.2 or current_price > 0.8:
                # Extreme prices with whale activity
                confidence += 0.1
        
        return min(confidence, 0.95)
    
    def _determine_whale_direction(self, market: Dict, price: float) -> str:
        """
        Determine which direction whales are betting
        """
        # In real scenario, we'd track order flow
        # For now, use price momentum as proxy
        
        token_id = market.get('token_id')
        if token_id in self.whale_trades:
            prev_price = self.whale_trades[token_id].get('last_price', price)
            if price > prev_price:
                return 'BUY'  # Price rising = whales buying
            elif price < prev_price:
                return 'SELL'  # Price falling = whales selling
        
        # Default: follow the trend away from 0.5
        if price > 0.5:
            return 'BUY'  # Momentum up
        else:
            return 'SELL'  # Momentum down
    
    def _calculate_copycat_bet(self, whale_info: Dict, insider_confidence: float, direction: str) -> float:
        """
        Calculate bet size based on whale activity
        """
        base_bet = self.base_bet_percentage
        
        # Scale by whale score
        whale_multiplier = 1.0 + (whale_info['score'] / 10)
        
        # Scale by insider confidence
        insider_multiplier = 1.0 + insider_confidence
        
        # Impact-based scaling (bigger impact = bigger bet)
        if whale_info['liquidity'] > 0:
            impact = whale_info['volume'] / whale_info['liquidity']
            impact_multiplier = min(1.0 + (impact / 10), 2.0)
        else:
            impact_multiplier = 1.0
        
        final_bet = base_bet * whale_multiplier * insider_multiplier * impact_multiplier
        
        # Cap at 70% for single bet
        return min(final_bet, 0.7)
    
    def analyze_market(self, market: Dict) -> Optional[Dict]:
        try:
            token_id = market.get('token_id')
            if not token_id:
                return None
            
            price = self.get_market_price(token_id)
            if not price:
                return None
            
            # Detect whale activity
            is_whale, whale_info = self._detect_whale_activity(market)
            
            # Skip if no whale detected
            if not is_whale:
                # Still track for future reference
                self.whale_trades[token_id] = {
                    'last_volume': market.get('volume', 0),
                    'last_price': price,
                    'last_check': datetime.now()
                }
                return None
            
            # Detect insider patterns
            insider_confidence = self._detect_insider_patterns(market, whale_info)
            
            # Determine whale direction
            direction = self._determine_whale_direction(market, price)
            
            # Calculate bet size
            bet_percentage = self._calculate_copycat_bet(whale_info, insider_confidence, direction)
            
            # Adjust for current balance
            amount = min(
                self.current_balance * bet_percentage,
                self.current_balance * 0.8  # Never bet more than 80%
            )
            
            # Log whale detection
            self.logger.info(f"🐋 WHALE DETECTED: {market.get('question', '')[:40]}...")
            self.logger.info(f"   Volume: ${whale_info['volume']:,.0f} | "
                           f"Liquidity: ${whale_info['liquidity']:,.0f} | "
                           f"Impact: {whale_info['volume']/max(whale_info['liquidity'], 1):.1f}x")
            
            if insider_confidence > 0.5:
                self.logger.info(f"   🎯 POTENTIAL INSIDER: Confidence {insider_confidence:.2f}")
            
            self.logger.info(f"   Following {direction} with ${amount:.2f} "
                           f"({bet_percentage*100:.1f}% of balance)")
            
            # Update tracking
            self.whale_trades[token_id] = {
                'last_volume': market.get('volume', 0),
                'last_price': price,
                'last_check': datetime.now(),
                'whale_detected': True,
                'insider_confidence': insider_confidence
            }
            
            # Increase aggression if we're following multiple whales successfully
            successful_follows = sum(1 for t in self.whale_trades.values() 
                                   if t.get('whale_detected', False))
            if successful_follows > 3:
                self.confidence_multiplier = min(self.confidence_multiplier * 1.1, 2.0)
            
            return {
                "token_id": token_id,
                "side": direction,
                "amount": amount * self.confidence_multiplier,
                "price": price
            }
            
        except Exception as e:
            self.logger.error(f"Whale analysis error: {e}")
            return None
    
    def should_continue(self) -> bool:
        # Very aggressive - continue until 1% of initial balance
        if self.current_balance < self.initial_balance * 0.01:
            return False
        
        # If we're up big, get more aggressive
        if self.current_balance > self.initial_balance * 5:
            self.base_bet_percentage = 0.5
            self.logger.info("🚀 Increasing whale following aggression!")
        
        # Clean old whale data
        now = datetime.now()
        old_tokens = []
        for token_id, data in self.whale_trades.items():
            if now - data.get('last_check', now) > timedelta(hours=2):
                old_tokens.append(token_id)
        
        for token_id in old_tokens:
            del self.whale_trades[token_id]
        
        return True
