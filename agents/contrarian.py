import random
from typing import Dict, Optional
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from base_agent import BaseAgent

class Contrarian(BaseAgent):
    """
    Contrarian: Bets against the consensus and popular opinion.
    Strategy: When everyone zigs, this agent zags. Fades the public.
    """
    
    def __init__(self, initial_balance: float = 10.0):
        super().__init__("Contrarian", initial_balance)
        self.min_balance_threshold = 1.0
        self.bet_percentage = 0.18
        self.consensus_threshold = 0.70
        
    def analyze_market(self, market: Dict) -> Optional[Dict]:
        if random.random() > 0.35:
            return None
        
        tokens = market.get('tokens', [])
        if not tokens or len(tokens) < 2:
            return None
        
        for token in tokens:
            token_id = token.get('token_id')
            if not token_id:
                continue
            
            current_price = self.get_market_price(token_id)
            if not current_price:
                continue
            
            if current_price > self.consensus_threshold and current_price < 0.95:
                bet_amount = self.current_balance * self.bet_percentage
                bet_amount = max(0.5, min(bet_amount, self.current_balance))
                
                target_price = current_price * 0.97
                
                self.logger.info(f"🔄 Contrarian bet: {market.get('question', 'Unknown')[:60]}... | "
                               f"${bet_amount:.2f} SELL @ {target_price:.3f} (fading {current_price:.3f})")
                
                return {
                    "token_id": token_id,
                    "side": "SELL",
                    "amount": bet_amount,
                    "price": target_price
                }
            
            elif current_price < (1 - self.consensus_threshold) and current_price > 0.05:
                bet_amount = self.current_balance * self.bet_percentage
                bet_amount = max(0.5, min(bet_amount, self.current_balance))
                
                target_price = current_price * 1.03
                
                self.logger.info(f"🔄 Contrarian bet: {market.get('question', 'Unknown')[:60]}... | "
                               f"${bet_amount:.2f} BUY @ {target_price:.3f} (fading {current_price:.3f})")
                
                return {
                    "token_id": token_id,
                    "side": "BUY",
                    "amount": bet_amount,
                    "price": target_price
                }
        
        return None
    
    def should_continue(self) -> bool:
        return self.current_balance >= self.min_balance_threshold
