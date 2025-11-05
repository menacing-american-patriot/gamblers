import random
from typing import Dict, Optional
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from base_agent import BaseAgent

class YOLOAgent(BaseAgent):
    """
    YOLO Agent: Goes all-in on random markets with high conviction.
    Strategy: Maximum risk, maximum potential reward. Bets big on gut feelings.
    """
    
    def __init__(self, initial_balance: float = 10.0):
        super().__init__("YOLO_Agent", initial_balance)
        self.min_balance_threshold = 0.5
        self.bet_percentage = 0.3
        
    def analyze_market(self, market: Dict) -> Optional[Dict]:
        if random.random() > 0.85:
            return None
        
        tokens = market.get('tokens', [])
        if not tokens or len(tokens) < 2:
            return None
        
        token = random.choice(tokens)
        token_id = token.get('token_id')
        
        if not token_id:
            return None
        
        current_price = self.get_market_price(token_id)
        if not current_price or current_price <= 0.01 or current_price >= 0.99:
            return None
        
        bet_amount = self.current_balance * self.bet_percentage
        bet_amount = max(0.5, min(bet_amount, self.current_balance))
        
        side = "BUY" if random.random() > 0.5 else "SELL"
        
        price_adjustment = random.uniform(0.95, 1.05)
        target_price = min(0.99, max(0.01, current_price * price_adjustment))
        
        self.logger.info(f"🎲 YOLO pick: {market.get('question', 'Unknown')[:60]}... | "
                        f"Betting ${bet_amount:.2f} on {side}")
        
        return {
            "token_id": token_id,
            "side": side,
            "amount": bet_amount,
            "price": target_price
        }
    
    def should_continue(self) -> bool:
        return self.current_balance >= self.min_balance_threshold
