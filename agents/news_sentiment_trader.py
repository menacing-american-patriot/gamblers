"""
News & Sentiment Trader - Makes rapid trades based on market sentiment shifts
Detects trending topics and rides waves of public opinion
"""
from typing import Dict, Optional, List
from base_agent import BaseAgent
import random
from datetime import datetime, timedelta

class NewsSentimentTrader(BaseAgent):
    def __init__(self, name: str = "NewsSentimentTrader", initial_balance: float = 10.0, register_with_portfolio: bool = True):
        super().__init__(name, initial_balance, register_with_portfolio=register_with_portfolio)
        self.sentiment_history = {}
        self.trending_topics = set()
        self.base_bet_percentage = 0.3
        self.momentum_multiplier = 1.0
        self.last_check_time = datetime.now()
        
    def _detect_trending(self, market: Dict) -> bool:
        """Detect if a market is trending based on volume and activity"""
        volume = market.get('volume', 0)
        liquidity = market.get('liquidity', 0)
        num_traders = market.get('num_traders', 0)
        
        # High activity indicators
        trending_score = 0
        
        if volume > 100000:
            trending_score += 3
        elif volume > 50000:
            trending_score += 2
        elif volume > 20000:
            trending_score += 1
        
        if liquidity > 20000:
            trending_score += 2
        elif liquidity > 10000:
            trending_score += 1
        
        if num_traders > 500:
            trending_score += 2
        elif num_traders > 200:
            trending_score += 1
        
        return trending_score >= 4
    
    def _analyze_sentiment_shift(self, token_id: str, current_price: float) -> Dict:
        """Analyze if sentiment is shifting"""
        if token_id not in self.sentiment_history:
            self.sentiment_history[token_id] = []
        
        history = self.sentiment_history[token_id]
        history.append({
            'price': current_price,
            'time': datetime.now()
        })
        
        # Keep only recent history (last 10 entries)
        if len(history) > 10:
            history = history[-10:]
            self.sentiment_history[token_id] = history
        
        if len(history) < 2:
            return {'shift': 'neutral', 'strength': 0}
        
        # Calculate momentum
        recent_prices = [h['price'] for h in history[-5:]]
        older_prices = [h['price'] for h in history[:-5]] if len(history) > 5 else [history[0]['price']]
        
        avg_recent = sum(recent_prices) / len(recent_prices)
        avg_older = sum(older_prices) / len(older_prices)
        
        change = (avg_recent - avg_older) / avg_older if avg_older > 0 else 0
        
        if change > 0.1:  # 10% increase
            return {'shift': 'bullish', 'strength': min(abs(change), 1.0)}
        elif change < -0.1:  # 10% decrease
            return {'shift': 'bearish', 'strength': min(abs(change), 1.0)}
        else:
            return {'shift': 'neutral', 'strength': abs(change)}
    
    def _get_topic_keywords(self, question: str) -> List[str]:
        """Extract topic keywords for sentiment tracking"""
        keywords = []
        text = question.lower()
        
        # Hot topics that often have sentiment swings
        hot_topics = {
            'trump': ['trump', 'donald', 'maga'],
            'biden': ['biden', 'joe biden'],
            'election': ['election', 'electoral', 'vote', 'ballot'],
            'crypto': ['bitcoin', 'ethereum', 'crypto', 'btc', 'eth'],
            'ai': ['ai', 'artificial intelligence', 'chatgpt', 'openai'],
            'war': ['war', 'ukraine', 'russia', 'conflict'],
            'economy': ['inflation', 'recession', 'fed', 'rates', 'economy'],
            'sports': ['nfl', 'nba', 'super bowl', 'championship', 'playoffs']
        }
        
        for topic, terms in hot_topics.items():
            for term in terms:
                if term in text:
                    keywords.append(topic)
                    break
        
        return keywords
    
    def _calculate_sentiment_bet(self, sentiment: Dict, price: float, is_trending: bool) -> Dict:
        """Calculate bet based on sentiment analysis"""
        shift = sentiment['shift']
        strength = sentiment['strength']
        
        # Base decision on sentiment shift
        if shift == 'bullish':
            if price < 0.7:  # Room to grow
                action = 'BUY'
                confidence = 0.6 + (strength * 0.3)
            else:  # Might be overheated
                action = 'SELL'
                confidence = 0.4 + (strength * 0.2)
        elif shift == 'bearish':
            if price > 0.3:  # Room to fall
                action = 'SELL'
                confidence = 0.6 + (strength * 0.3)
            else:  # Might be oversold
                action = 'BUY'
                confidence = 0.4 + (strength * 0.2)
        else:  # Neutral sentiment
            # Bet on mean reversion
            if price < 0.3:
                action = 'BUY'
                confidence = 0.5
            elif price > 0.7:
                action = 'SELL'
                confidence = 0.5
            else:
                # Random exploration
                action = 'BUY' if random.random() < 0.5 else 'SELL'
                confidence = 0.3
        
        # Boost confidence for trending markets
        if is_trending:
            confidence = min(confidence * 1.3, 0.95)
        
        return {'action': action, 'confidence': confidence}
    
    def analyze_market(self, market: Dict) -> Optional[Dict]:
        try:
            token_id = market.get('token_id')
            if not token_id:
                return None
            
            price = self.get_market_price(token_id)
            if not price:
                return None
            
            # Check if market is trending
            is_trending = self._detect_trending(market)
            
            # Analyze sentiment shift
            sentiment = self._analyze_sentiment_shift(token_id, price)
            
            # Get topic keywords
            keywords = self._get_topic_keywords(market.get('question', ''))
            
            # Calculate bet
            bet_decision = self._calculate_sentiment_bet(sentiment, price, is_trending)
            
            # Skip low confidence bets unless trending
            if bet_decision['confidence'] < 0.5 and not is_trending:
                return None
            
            # Calculate bet size
            bet_percentage = self.base_bet_percentage * bet_decision['confidence']
            
            # Boost for trending markets
            if is_trending:
                bet_percentage *= 1.5
                self.logger.info(f"🔥 TRENDING: {market.get('question', '')[:50]}...")
            
            # Extra boost for hot topics
            if keywords:
                bet_percentage *= 1.2
                self.logger.info(f"🎯 Hot topic detected: {', '.join(keywords)}")
            
            # Momentum adjustment
            if sentiment['shift'] != 'neutral':
                self.momentum_multiplier = min(self.momentum_multiplier * 1.1, 2.0)
            else:
                self.momentum_multiplier = max(self.momentum_multiplier * 0.95, 1.0)
            
            bet_percentage *= self.momentum_multiplier
            
            # Cap at 60% of balance for single bet
            amount = min(
                self.current_balance * bet_percentage,
                self.current_balance * 0.6
            )
            
            self.logger.info(f"📰 Sentiment: {sentiment['shift']} ({sentiment['strength']:.2f}) | "
                           f"Proposing {bet_decision['action']} | "
                           f"Confidence: {bet_decision['confidence']:.2f}")
            
            proposal = {
                "token_id": token_id,
                "side": bet_decision['action'],
                "amount": amount,
                "price": price
            }
            return self.manage_with_llm(market, proposal, "Sentiment Trader")
            
        except Exception as e:
            self.logger.error(f"Sentiment analysis error: {e}")
            return None
    
    def should_continue(self) -> bool:
        # Aggressive continuation - go until 3% of initial
        if self.current_balance < self.initial_balance * 0.03:
            return False
        
        # If doing well, increase aggression
        if self.current_balance > self.initial_balance * 3:
            self.base_bet_percentage = 0.4
            self.logger.info("📈 Increasing aggression due to profits!")
        
        # Clear old sentiment data periodically
        now = datetime.now()
        if now - self.last_check_time > timedelta(minutes=30):
            old_tokens = []
            for token_id, history in self.sentiment_history.items():
                if history and now - history[-1]['time'] > timedelta(hours=1):
                    old_tokens.append(token_id)
            
            for token_id in old_tokens:
                del self.sentiment_history[token_id]
            
            self.last_check_time = now
            if old_tokens:
                self.logger.info(f"🧹 Cleared {len(old_tokens)} old sentiment records")
        
        return True
