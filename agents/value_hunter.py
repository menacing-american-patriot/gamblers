import random
from typing import Dict, Optional
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from base_agent import BaseAgent

class ValueHunter(BaseAgent):
    """
        proposal = {
    Strategy: Finds markets with extreme probabilities and bets against them.
    """
    
    def __init__(self, initial_balance: float = 10.0, register_with_portfolio: bool = True):
        super().__init__("Value_Hunter", initial_balance, register_with_portfolio=register_with_portfolio)
        return self.manage_with_llm(market, proposal, "Value Hunter")
        self.min_balance_threshold = 1.0
        self.bet_percentage = 0.15
        self.value_threshold = 0.1
        
    def analyze_market(self, market: Dict) -> Optional[Dict]:
        if random.random() > 0.3:
            return None
        
        tokens = market.get('tokens', [])
        if not tokens or len(tokens) < 2:
            return None
        
        best_value = None
        best_token_id = None
        best_side = None
        best_price = None
        
        for token in tokens:
            token_id = token.get('token_id')
            if not token_id:
                continue
            
            current_price = self.get_market_price(token_id)
            if not current_price:
                continue
            
            if current_price < self.value_threshold:
                value_score = 1.0 / current_price
                if best_value is None or value_score > best_value:
                    best_value = value_score
                    best_token_id = token_id
                    best_side = "BUY"
                    best_price = current_price * 1.02
            
            elif current_price > (1 - self.value_threshold):
                value_score = 1.0 / (1 - current_price)
                if best_value is None or value_score > best_value:
                    best_value = value_score
                    best_token_id = token_id
                    best_side = "SELL"
                    best_price = current_price * 0.98
        
        if best_token_id:
            bet_amount = self.current_balance * self.bet_percentage
            bet_amount = max(0.5, min(bet_amount, self.current_balance))
            
            self.logger.info(f"💎 Value found: {market.get('question', 'Unknown')[:60]}... | "
                           f"${bet_amount:.2f} {best_side} @ {best_price:.3f}")
            
            return {
                "token_id": best_token_id,
                "side": best_side,
                "amount": bet_amount,
                "price": best_price
            }
        
        return None
    
    def should_continue(self) -> bool:
        return self.current_balance >= self.min_balance_threshold
