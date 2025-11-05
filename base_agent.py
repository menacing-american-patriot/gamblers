import os
import logging
import time
from abc import ABC, abstractmethod
from typing import List, Dict, Optional
from py_clob_client.client import ClobClient
from py_clob_client.clob_types import OrderArgs, OrderType
from datetime import datetime

class BaseAgent(ABC):
    def __init__(self, name: str, initial_balance: float, host: str = "https://clob.polymarket.com"):
        self.name = name
        self.initial_balance = initial_balance
        self.current_balance = initial_balance
        self.host = host
        self.trades_made = 0
        self.winning_trades = 0
        self.losing_trades = 0
        
        self.logger = logging.getLogger(name)
        self.logger.setLevel(logging.INFO)
        
        os.makedirs("agent_logs", exist_ok=True)
        fh = logging.FileHandler(f"agent_logs/{name}.log")
        fh.setLevel(logging.INFO)
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        fh.setFormatter(formatter)
        self.logger.addHandler(fh)
        
        ch = logging.StreamHandler()
        ch.setLevel(logging.INFO)
        ch.setFormatter(formatter)
        self.logger.addHandler(ch)
        
        self.client = None
        self._init_client()
        
    def _init_client(self):
        try:
            private_key = os.getenv("PRIVATE_KEY")
            if not private_key:
                raise ValueError("PRIVATE_KEY not found in environment")
            
            self.client = ClobClient(
                self.host,
                key=private_key,
                chain_id=137
            )
            self.logger.info(f"{self.name} initialized successfully")
        except Exception as e:
            self.logger.error(f"Failed to initialize client: {e}")
            raise
    
    def get_active_markets(self, limit: int = 100) -> List[Dict]:
        try:
            markets = self.client.get_markets()
            return [m for m in markets if m.get('active', False)][:limit]
        except Exception as e:
            self.logger.error(f"Error fetching markets: {e}")
            return []
    
    def get_market_price(self, token_id: str) -> Optional[float]:
        try:
            book = self.client.get_order_book(token_id)
            if book and 'bids' in book and len(book['bids']) > 0:
                return float(book['bids'][0]['price'])
            return None
        except Exception as e:
            self.logger.error(f"Error fetching price for {token_id}: {e}")
            return None
    
    def place_bet(self, token_id: str, side: str, amount: float, price: float) -> bool:
        try:
            if amount > self.current_balance:
                self.logger.warning(f"Insufficient balance for bet: ${amount:.2f} > ${self.current_balance:.2f}")
                return False
            
            order_args = OrderArgs(
                token_id=token_id,
                price=price,
                size=amount / price,
                side=side,
                fee_rate_bps=0
            )
            
            signed_order = self.client.create_order(order_args)
            resp = self.client.post_order(signed_order, OrderType.GTC)
            
            if resp and resp.get('success'):
                self.current_balance -= amount
                self.trades_made += 1
                self.logger.info(f"✓ Placed {side} bet: ${amount:.2f} @ {price:.3f} on {token_id[:8]}...")
                return True
            else:
                self.logger.warning(f"Order placement failed: {resp}")
                return False
                
        except Exception as e:
            self.logger.error(f"Error placing bet: {e}")
            return False
    
    def get_stats(self) -> Dict:
        profit = self.current_balance - self.initial_balance
        roi = (profit / self.initial_balance * 100) if self.initial_balance > 0 else 0
        
        return {
            "name": self.name,
            "initial_balance": self.initial_balance,
            "current_balance": self.current_balance,
            "profit": profit,
            "roi": roi,
            "trades_made": self.trades_made,
            "winning_trades": self.winning_trades,
            "losing_trades": self.losing_trades
        }
    
    def log_stats(self):
        stats = self.get_stats()
        self.logger.info(f"📊 Stats - Balance: ${stats['current_balance']:.2f} | "
                        f"P/L: ${stats['profit']:.2f} ({stats['roi']:.1f}%) | "
                        f"Trades: {stats['trades_made']}")
    
    @abstractmethod
    def analyze_market(self, market: Dict) -> Optional[Dict]:
        """
        Analyze a market and return betting decision
        Returns: {"token_id": str, "side": "BUY"/"SELL", "amount": float, "price": float} or None
        """
        pass
    
    @abstractmethod
    def should_continue(self) -> bool:
        """Determine if agent should continue trading"""
        pass
    
    def run(self, max_iterations: int = 50, sleep_time: int = 30):
        self.logger.info(f"🚀 {self.name} starting with ${self.initial_balance:.2f}")
        
        iteration = 0
        while iteration < max_iterations and self.should_continue():
            try:
                markets = self.get_active_markets()
                if not markets:
                    self.logger.warning("No active markets found")
                    time.sleep(sleep_time)
                    continue
                
                for market in markets:
                    if not self.should_continue():
                        break
                    
                    decision = self.analyze_market(market)
                    if decision:
                        self.place_bet(
                            decision['token_id'],
                            decision['side'],
                            decision['amount'],
                            decision['price']
                        )
                        time.sleep(2)
                
                self.log_stats()
                iteration += 1
                
                if iteration < max_iterations and self.should_continue():
                    time.sleep(sleep_time)
                    
            except Exception as e:
                self.logger.error(f"Error in main loop: {e}")
                time.sleep(sleep_time)
        
        self.logger.info(f"🏁 {self.name} finished")
        self.log_stats()
        return self.get_stats()
