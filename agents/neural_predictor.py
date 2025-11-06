"""
Neural Network-inspired agent that learns from market patterns
Uses simple pattern recognition and adapts betting based on success rate
"""
import random
import numpy as np
from typing import Dict, Optional, List
from base_agent import BaseAgent

class NeuralPredictor(BaseAgent):
    def __init__(self, name: str = "NeuralPredictor", initial_balance: float = 10.0, register_with_portfolio: bool = True):
        super().__init__(name, initial_balance, register_with_portfolio=register_with_portfolio)
        self.market_memory = {}  # Store market patterns
        self.success_weights = {}  # Track which patterns work
        self.confidence_threshold = 0.65
        self.base_bet_percentage = 0.25
        self.learning_rate = 0.1
        self.pattern_history = []
        self.max_bet_percentage = 0.5  # Can bet up to 50% when confident
        
    def _extract_features(self, market: Dict) -> tuple:
        """Extract key features from market for pattern matching"""
        try:
            volume = market.get('volume', 0)
            liquidity = market.get('liquidity', 0)
            num_traders = market.get('num_traders', 0)
            
            # Create feature vector
            features = (
                volume > 10000,  # High volume
                liquidity > 5000,  # Good liquidity
                num_traders > 100,  # Many participants
                'politics' in market.get('question', '').lower(),
                'sports' in market.get('question', '').lower(),
                'crypto' in market.get('question', '').lower(),
            )
            return features
        except:
            return tuple()
    
    def _calculate_confidence(self, market: Dict, price: float) -> float:
        """Calculate confidence based on market features and past success"""
        features = self._extract_features(market)
        
        # Check if we've seen similar patterns
        if features in self.success_weights:
            base_confidence = self.success_weights[features]
        else:
            base_confidence = 0.5
        
        # Adjust for extreme prices (more confident at extremes)
        if price < 0.1 or price > 0.9:
            confidence_boost = 0.2
        elif price < 0.2 or price > 0.8:
            confidence_boost = 0.1
        else:
            confidence_boost = 0
        
        # Market volatility factor
        volume = market.get('volume', 0)
        if volume > 50000:
            confidence_boost += 0.15
        elif volume > 20000:
            confidence_boost += 0.1
        
        return min(base_confidence + confidence_boost, 0.95)
    
    def _kelly_bet_size(self, confidence: float, odds: float) -> float:
        """Calculate optimal bet size using Kelly Criterion"""
        # Kelly formula: f = (p*b - q)/b
        # where p = probability of winning, b = odds, q = probability of losing
        p = confidence
        q = 1 - p
        b = odds - 1 if odds > 1 else 1 / (1 - odds) - 1
        
        kelly_fraction = (p * b - q) / b if b > 0 else 0
        
        # Apply fractional Kelly (25%) for safety
        safe_kelly = kelly_fraction * 0.25
        
        # Cap between min and max percentages
        return max(self.base_bet_percentage, min(safe_kelly, self.max_bet_percentage))
    
    def _update_learning(self, features: tuple, success: bool):
        """Update success weights based on outcome"""
        if features not in self.success_weights:
            self.success_weights[features] = 0.5
        
        # Simple learning update
        current = self.success_weights[features]
        if success:
            self.success_weights[features] = current + self.learning_rate * (1 - current)
        else:
            self.success_weights[features] = current - self.learning_rate * current
        
        # Keep weights in reasonable range
        self.success_weights[features] = max(0.1, min(0.9, self.success_weights[features]))
    
    def analyze_market(self, market: Dict) -> Optional[Dict]:
        try:
            token_id = market.get('token_id')
            if not token_id:
                return None
            
            price = self.get_market_price(token_id)
            if not price:
                return None
            
            # Calculate confidence
            confidence = self._calculate_confidence(market, price)
            
            # Skip if confidence too low
            if confidence < self.confidence_threshold:
                return None
            
            # Determine side based on price and patterns
            features = self._extract_features(market)
            
            # Neural-inspired decision: combine multiple signals
            signals = []
            
            # Price extreme signal
            if price < 0.15:
                signals.append(('BUY', 0.8))
            elif price > 0.85:
                signals.append(('SELL', 0.8))
            
            # Momentum signal (if we have history)
            if token_id in self.market_memory:
                last_price = self.market_memory[token_id]
                if price > last_price * 1.05:  # 5% increase
                    signals.append(('BUY', 0.6))
                elif price < last_price * 0.95:  # 5% decrease
                    signals.append(('SELL', 0.6))
            
            # Pattern-based signal
            if features in self.success_weights and self.success_weights[features] > 0.6:
                # Use contrarian for high-confidence patterns
                if price > 0.6:
                    signals.append(('SELL', self.success_weights[features]))
                else:
                    signals.append(('BUY', self.success_weights[features]))
            
            # Combine signals
            if not signals:
                # Random exploration with bias
                side = 'BUY' if random.random() < (1 - price) else 'SELL'
            else:
                # Weighted voting
                buy_weight = sum(w for s, w in signals if s == 'BUY')
                sell_weight = sum(w for s, w in signals if s == 'SELL')
                side = 'BUY' if buy_weight > sell_weight else 'SELL'
            
            # Calculate bet size using Kelly criterion
            odds = price if side == 'SELL' else (1 - price)
            bet_percentage = self._kelly_bet_size(confidence, odds)
            amount = min(self.current_balance * bet_percentage, self.current_balance * 0.9)
            
            # Store for learning
            self.market_memory[token_id] = price
            self.pattern_history.append((features, side, confidence))
            
            # Aggressive adjustment for high confidence
            if confidence > 0.85:
                amount *= 1.5  # 50% boost for high confidence
            
            self.logger.info(f"🧠 Neural analysis: {market.get('question', '')[:50]}... "
                           f"Confidence: {confidence:.2f}, Proposed bet: {bet_percentage:.1%}")
            
            proposal = {
                "token_id": token_id,
                "side": side,
                "amount": amount,
                "price": price
            }
            return self.manage_with_llm(market, proposal, "Neural Predictor")
            
        except Exception as e:
            self.logger.error(f"Analysis error: {e}")
            return None
    
    def should_continue(self) -> bool:
        # Continue if we have at least 5% of initial balance
        # or if we're up significantly (to ride the wave)
        if self.current_balance < self.initial_balance * 0.05:
            return False
        
        # If we're up 5x, become more aggressive
        if self.current_balance > self.initial_balance * 5:
            self.max_bet_percentage = 0.7  # Increase max bet to 70%
            self.confidence_threshold = 0.55  # Lower threshold
        
        return True
