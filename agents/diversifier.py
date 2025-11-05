import random
from typing import Dict, Optional, Set
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from base_agent import BaseAgent

class Diversifier(BaseAgent):
    """
    Diversifier: Spreads small bets across many different markets.
    Strategy: Portfolio approach - minimize risk through diversification.
    """
    
    def __init__(self, initial_balance: float = 10.0):
        super().__init__("Diversifier", initial_balance)
        self.min_balance_threshold = 0.5
        self.bet_percentage = 0.05
        self.markets_traded: Set[str] = set()
        self.max_markets = 20
        
    def analyze_market(self, market: Dict) -> Optional[Dict]:
        market_id = market.get('condition_id', '')
        
        if market_id in self.markets_traded:
            return None
        
        if len(self.markets_traded) >= self.max_markets:
            return None
        
        if random.random() > 0.5:
            return None
        
        tokens = market.get('tokens', [])
        if not tokens or len(tokens) < 2:
            return None
        
        token = random.choice(tokens)
        token_id = token.get('token_id')
        
        if not token_id:
            return None
        
        current_price = self.get_market_price(token_id)
        if not current_price or current_price <= 0.05 or current_price >= 0.95:
            return None
        
        bet_amount = self.current_balance * self.bet_percentage
        bet_amount = max(0.25, min(bet_amount, self.current_balance))
        
        side = "BUY" if current_price < 0.5 else "SELL"
        
        target_price = current_price * (1.01 if side == "BUY" else 0.99)
        target_price = min(0.99, max(0.01, target_price))
        
        self.markets_traded.add(market_id)
        
        self.logger.info(f"🎯 Diversifying: {market.get('question', 'Unknown')[:60]}... | "
                        f"${bet_amount:.2f} {side} (market {len(self.markets_traded)}/{self.max_markets})")
        
        return {
            "token_id": token_id,
            "side": side,
            "amount": bet_amount,
            "price": target_price
        }
    
    def should_continue(self) -> bool:
        return (self.current_balance >= self.min_balance_threshold and 
                len(self.markets_traded) < self.max_markets)
