"""
Arbitrage Hunter - Looks for pricing inefficiencies across related markets
Exploits logical inconsistencies and correlated events
"""
from typing import Dict, Optional, List
from base_agent import BaseAgent
import random

class ArbitrageHunter(BaseAgent):
    def __init__(self, name: str = "ArbitrageHunter", initial_balance: float = 10.0):
        super().__init__(name, initial_balance)
        self.market_cache = {}
        self.correlation_map = {}
        self.base_bet_percentage = 0.35  # Aggressive when arbitrage found
        self.arbitrage_threshold = 0.1  # 10% price difference threshold
        self.seen_markets = set()
        
    def _find_correlated_markets(self, markets: List[Dict]) -> Dict[str, List[str]]:
        """Find markets that should be correlated"""
        correlations = {}
        
        for market in markets:
            question = market.get('question', '').lower()
            token_id = market.get('token_id')
            
            if not token_id:
                continue
            
            # Look for similar keywords
            keywords = self._extract_keywords(question)
            
            for keyword in keywords:
                if keyword not in correlations:
                    correlations[keyword] = []
                correlations[keyword].append(token_id)
        
        # Filter to only groups with multiple markets
        return {k: v for k, v in correlations.items() if len(v) > 1}
    
    def _extract_keywords(self, text: str) -> List[str]:
        """Extract key terms for correlation"""
        important_words = []
        
        # Political figures
        politicians = ['trump', 'biden', 'desantis', 'newsom', 'kennedy']
        for pol in politicians:
            if pol in text:
                important_words.append(pol)
        
        # Events
        events = ['election', 'super bowl', 'world cup', 'olympics', 'primary']
        for event in events:
            if event in text:
                important_words.append(event)
        
        # Time periods
        if '2024' in text:
            important_words.append('2024')
        if '2025' in text:
            important_words.append('2025')
        
        # Categories
        if 'democrat' in text or 'republican' in text:
            important_words.append('politics')
        if 'nfl' in text or 'nba' in text or 'sports' in text:
            important_words.append('sports')
        if 'bitcoin' in text or 'ethereum' in text or 'crypto' in text:
            important_words.append('crypto')
        
        return important_words
    
    def _check_logical_inconsistency(self, market1: Dict, market2: Dict, price1: float, price2: float) -> Optional[str]:
        """Check if two markets have logically inconsistent prices"""
        q1 = market1.get('question', '').lower()
        q2 = market2.get('question', '').lower()
        
        # Check for mutually exclusive events
        if 'win' in q1 and 'win' in q2:
            # If both are about winning same thing, probabilities shouldn't sum > 1
            if price1 + price2 > 1.1:  # Allow 10% margin
                return 'exclusive_sum'
        
        # Check for same event, different framing
        similarity = self._calculate_similarity(q1, q2)
        if similarity > 0.7:
            # Very similar questions should have similar prices
            if abs(price1 - price2) > self.arbitrage_threshold:
                return 'similar_different'
        
        # Check for complement events
        if ('not' in q1 and q1.replace('not ', '') == q2) or \
           ('not' in q2 and q2.replace('not ', '') == q1):
            # Complementary events should sum to ~1
            if abs((price1 + price2) - 1.0) > 0.15:
                return 'complement_mismatch'
        
        return None
    
    def _calculate_similarity(self, text1: str, text2: str) -> float:
        """Simple similarity calculation"""
        words1 = set(text1.split())
        words2 = set(text2.split())
        
        if not words1 or not words2:
            return 0
        
        intersection = words1.intersection(words2)
        union = words1.union(words2)
        
        return len(intersection) / len(union)
    
    def _calculate_arbitrage_bet(self, inconsistency_type: str, price1: float, price2: float) -> Dict:
        """Calculate optimal arbitrage bet"""
        if inconsistency_type == 'exclusive_sum':
            # Both events can't happen, bet against both
            if price1 > price2:
                return {'action': 'SELL', 'confidence': 0.9, 'target_price': price1}
            else:
                return {'action': 'SELL', 'confidence': 0.9, 'target_price': price2}
        
        elif inconsistency_type == 'similar_different':
            # Similar events with different prices - bet on convergence
            avg_price = (price1 + price2) / 2
            if price1 > avg_price + 0.05:
                return {'action': 'SELL', 'confidence': 0.75, 'target_price': price1}
            else:
                return {'action': 'BUY', 'confidence': 0.75, 'target_price': price1}
        
        elif inconsistency_type == 'complement_mismatch':
            # Complementary events not summing to 1
            total = price1 + price2
            if total > 1.0:
                # Overpriced - sell the higher one
                return {'action': 'SELL', 'confidence': 0.85, 
                       'target_price': max(price1, price2)}
            else:
                # Underpriced - buy the lower one
                return {'action': 'BUY', 'confidence': 0.85,
                       'target_price': min(price1, price2)}
        
        return {'action': 'BUY', 'confidence': 0.5, 'target_price': price1}
    
    def analyze_market(self, market: Dict) -> Optional[Dict]:
        try:
            token_id = market.get('token_id')
            if not token_id or token_id in self.seen_markets:
                return None
            
            price = self.get_market_price(token_id)
            if not price:
                return None
            
            # Store market info
            self.market_cache[token_id] = {
                'market': market,
                'price': price
            }
            
            # Look for arbitrage opportunities
            best_opportunity = None
            best_confidence = 0
            
            for other_token_id, other_data in self.market_cache.items():
                if other_token_id == token_id:
                    continue
                
                other_market = other_data['market']
                other_price = other_data['price']
                
                # Check for logical inconsistency
                inconsistency = self._check_logical_inconsistency(
                    market, other_market, price, other_price
                )
                
                if inconsistency:
                    arb_bet = self._calculate_arbitrage_bet(inconsistency, price, other_price)
                    
                    if arb_bet['confidence'] > best_confidence:
                        best_opportunity = {
                            'token_id': token_id,
                            'side': arb_bet['action'],
                            'confidence': arb_bet['confidence'],
                            'price': price,
                            'reason': inconsistency
                        }
                        best_confidence = arb_bet['confidence']
            
            # If no arbitrage found, look for simple mispricing
            if not best_opportunity:
                # Extreme prices often correct
                if price < 0.05:
                    best_opportunity = {
                        'token_id': token_id,
                        'side': 'BUY',
                        'confidence': 0.7,
                        'price': price,
                        'reason': 'extreme_low'
                    }
                elif price > 0.95:
                    best_opportunity = {
                        'token_id': token_id,
                        'side': 'SELL',
                        'confidence': 0.7,
                        'price': price,
                        'reason': 'extreme_high'
                    }
            
            if best_opportunity and best_opportunity['confidence'] > 0.6:
                # Calculate bet size based on confidence
                bet_percentage = self.base_bet_percentage * best_opportunity['confidence']
                
                # Boost for high-confidence arbitrage
                if best_opportunity['confidence'] > 0.85:
                    bet_percentage *= 1.5
                
                amount = min(
                    self.current_balance * bet_percentage,
                    self.current_balance * 0.8  # Never bet more than 80%
                )
                
                self.seen_markets.add(token_id)
                
                self.logger.info(f"💎 Arbitrage found: {best_opportunity['reason']} | "
                               f"{market.get('question', '')[:40]}... | "
                               f"Confidence: {best_opportunity['confidence']:.2f}")
                
                return {
                    "token_id": token_id,
                    "side": best_opportunity['side'],
                    "amount": amount,
                    "price": best_opportunity['price']
                }
            
            return None
            
        except Exception as e:
            self.logger.error(f"Arbitrage analysis error: {e}")
            return None
    
    def should_continue(self) -> bool:
        # Very aggressive - continue until 2% of initial balance
        if self.current_balance < self.initial_balance * 0.02:
            return False
        
        # Clear seen markets periodically for fresh opportunities
        if len(self.seen_markets) > 50:
            self.seen_markets.clear()
            self.logger.info("🔄 Clearing market history for fresh opportunities")
        
        return True
