import random
from typing import Dict, Optional
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from base_agent import BaseAgent

class MomentumChaser(BaseAgent):
    """
    Momentum Chaser: Follows the crowd and bets on trending outcomes.
    Strategy: Rides the wave of popular opinion, momentum trading style.
    """
    
    def __init__(self, initial_balance: float = 10.0, register_with_portfolio: bool = True):
        super().__init__("Momentum_Chaser", initial_balance, register_with_portfolio=register_with_portfolio)
        self.min_balance_threshold = 1.0
        self.bet_percentage = 0.2
        self.momentum_threshold = 0.65
        
    def analyze_market(self, market: Dict) -> Optional[Dict]:
        if random.random() > 0.4:
            return None
        
        tokens = market.get('tokens', [])
        if not tokens or len(tokens) < 2:
            return None
        
        best_momentum = None
        best_token_id = None
        best_price = None
        
        for token in tokens:
            token_id = token.get('token_id')
            if not token_id:
                continue
            
            current_price = self.get_market_price(token_id)
            if not current_price:
                continue
            
            if current_price > self.momentum_threshold and current_price < 0.95:
                momentum_score = current_price
                if best_momentum is None or momentum_score > best_momentum:
                    best_momentum = momentum_score
                    best_token_id = token_id
                    best_price = current_price
        
        if best_token_id:
            bet_amount = self.current_balance * self.bet_percentage
            bet_amount = max(0.5, min(bet_amount, self.current_balance))
            
            target_price = min(0.99, best_price * 1.03)
            
            self.logger.info(f"📈 Momentum play: {market.get('question', 'Unknown')[:60]}... | "
                           f"Proposing ${bet_amount:.2f} BUY @ {target_price:.3f}")
            
            proposal = {
                "token_id": best_token_id,
                "side": "BUY",
                "amount": bet_amount,
                "price": target_price
            }
            return self.manage_with_llm(market, proposal, "Momentum Chaser")
        
        return None
    
    def should_continue(self) -> bool:
        return self.current_balance >= self.min_balance_threshold
