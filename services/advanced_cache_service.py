import logging
import hashlib
import time
import json
import re
from typing import Dict, List, Optional, Set
from collections import defaultdict
from services.cache_service import IntelligentCacheManager

logger = logging.getLogger(__name__)

class AdvancedCacheService:
    """
    Advanced caching service with:
    - Predictive caching for follow-up questions
    - Question variation recognition
    - Semantic similarity caching
    - Usage pattern analysis
    """
    
    def __init__(self, max_size=1000, default_ttl=3600):
        # Core cache manager
        self.cache_manager = IntelligentCacheManager(max_size, default_ttl)
        
        # Advanced features
        self.question_patterns = defaultdict(list)  # Track question patterns
        self.follow_up_patterns = defaultdict(list)  # Track follow-up questions
        self.semantic_clusters = defaultdict(set)   # Group similar questions
        
        # Performance tracking
        self.prediction_hits = 0
        self.pattern_matches = 0
        self.total_predictions = 0
        
        # Question variations database
        self.question_variations = self._build_variation_database()
        
    def _build_variation_database(self):
        """
        Build database of common question variations
        """
        variations = {
            # Pricing variations
            "pricing": [
                "מה המחיר", "כמה עולה", "מה העלות", "כמה זה עולה", "מחיר השירות",
                "what's the price", "how much does it cost", "pricing", "cost"
            ],
            
            # How it works variations  
            "how_it_works": [
                "איך זה עובד", "איך זה פועל", "מה התהליך", "איך המערכת עובדה",
                "how does it work", "how it works", "the process", "how does the system work"
            ],
            
            # Features variations
            "features": [
                "מה התכונות", "אילו פיצ'רים יש", "מה הפונקציות", "מה זה כולל",
                "what features", "what functionality", "features list", "capabilities"
            ],
            
            # Support variations
            "support": [
                "יש תמיכה", "איך מקבלים עזרה", "יש סאפורט", "תמיכה טכנית",
                "is there support", "customer support", "technical support", "help"
            ],
            
            # Implementation variations
            "implementation": [
                "כמה זמן לוקח ההטמעה", "תהליך היישום", "משך ההטמעה", "זמן הקמה",
                "implementation time", "how long to implement", "setup time", "deployment time"
            ]
        }
        
        # Create reverse mapping for quick lookup
        variation_map = {}
        for category, variations_list in variations.items():
            for variation in variations_list:
                variation_map[self._normalize_question(variation)] = category
                
        return variation_map
    
    def _normalize_question(self, question):
        """
        Normalize question for pattern matching
        """
        # Remove punctuation, convert to lowercase, strip whitespace
        normalized = re.sub(r'[^\w\s]', '', question.lower().strip())
        # Remove extra whitespace
        normalized = re.sub(r'\s+', ' ', normalized)
        return normalized
    
    def _get_question_category(self, question):
        """
        Categorize question for pattern matching
        """
        normalized = self._normalize_question(question)
        return self.question_variations.get(normalized, "unknown")
    
    def _generate_cache_keys(self, question):
        """
        Generate multiple cache keys for question variations
        """
        keys = []
        
        # Primary key
        primary_key = hashlib.md5(question.lower().encode()).hexdigest()
        keys.append(primary_key)
        
        # Normalized key
        normalized = self._normalize_question(question)
        normalized_key = hashlib.md5(normalized.encode()).hexdigest()
        if normalized_key not in keys:
            keys.append(normalized_key)
        
        # Category-based key
        category = self._get_question_category(question)
        if category != "unknown":
            category_key = hashlib.md5(f"category_{category}".encode()).hexdigest()
            keys.append(category_key)
        
        return keys
    
    def get(self, question, session=None):
        """
        Advanced cache retrieval with variation matching
        """
        # Try multiple cache keys
        cache_keys = self._generate_cache_keys(question)
        
        for key in cache_keys:
            result = self.cache_manager.get(key)
            if result:
                self.pattern_matches += 1
                logger.debug(f"[ADVANCED_CACHE] Hit for variation of: {question}")
                return result
        
        return None
    
    def set(self, question, response_data, session=None):
        """
        Advanced cache storage with predictive caching
        """
        # Store with multiple keys for better hit rate
        cache_keys = self._generate_cache_keys(question)
        
        for key in cache_keys:
            self.cache_manager.set(key, response_data)
        
        # Update patterns for predictive caching
        self._update_patterns(question, session)
        
        # Trigger predictive caching
        self._predictive_cache_related_questions(question, response_data)
        
        logger.debug(f"[ADVANCED_CACHE] Stored question with {len(cache_keys)} keys")
    
    def _update_patterns(self, question, session):
        """
        Update question patterns for learning
        """
        category = self._get_question_category(question)
        
        if session and "history" in session:
            history = session["history"]
            if len(history) > 0:
                previous_questions = [msg.get("content", "") for msg in history 
                                    if msg.get("role") == "user"]
                
                for prev_q in previous_questions[-3:]:  # Last 3 questions
                    if prev_q and prev_q != question:
                        prev_category = self._get_question_category(prev_q)
                        if prev_category != "unknown" and category != "unknown":
                            self.follow_up_patterns[prev_category].append(category)
    
    def _predictive_cache_related_questions(self, question, response_data):
        """
        Predictively cache likely follow-up questions
        """
        category = self._get_question_category(question)
        
        if category == "unknown":
            return
        
        # Common follow-up patterns
        follow_up_mapping = {
            "pricing": ["features", "implementation", "support"],
            "features": ["pricing", "implementation"],
            "how_it_works": ["pricing", "implementation"],
            "support": ["pricing", "implementation"],
            "implementation": ["support", "pricing"]
        }
        
        likely_follow_ups = follow_up_mapping.get(category, [])
        
        for follow_up_category in likely_follow_ups:
            # Find questions in this category
            category_questions = [q for q, cat in self.question_variations.items() 
                                if cat == follow_up_category]
            
            if category_questions:
                # Pre-warm with a related response hint
                for related_question in category_questions[:2]:  # Limit to 2
                    related_response = {
                        "answer": f"[מידע על {follow_up_category}] - נא לפנות לצוות המכירות לפרטים מדויקים",
                        "cached": True,
                        "predictive": True,
                        "source": "predictive_cache"
                    }
                    
                    cache_key = hashlib.md5(related_question.encode()).hexdigest()
                    self.cache_manager.set(cache_key, related_response, ttl=1800)  # 30 min TTL
                    
                self.total_predictions += len(category_questions[:2])
                logger.debug(f"[PREDICTIVE] Pre-cached {len(category_questions[:2])} questions for {follow_up_category}")
    
    def warm_cache_with_patterns(self, common_questions_responses):
        """
        Warm cache with common questions and their variations
        """
        warmed_count = 0
        
        for question, response in common_questions_responses.items():
            # Store the main question
            self.set(question, response)
            warmed_count += 1
            
            # Store variations
            category = self._get_question_category(question)
            if category != "unknown":
                variations = [q for q, cat in self.question_variations.items() 
                            if cat == category and q != self._normalize_question(question)]
                
                for variation in variations:
                    variation_key = hashlib.md5(variation.encode()).hexdigest()
                    self.cache_manager.set(variation_key, response)
                    warmed_count += 1
        
        logger.info(f"[ADVANCED_CACHE] Warmed cache with {warmed_count} entries including variations")
        return warmed_count
    
    def get_advanced_stats(self):
        """
        Get advanced caching statistics
        """
        base_stats = self.cache_manager.get_stats()
        
        prediction_success_rate = (self.prediction_hits / max(self.total_predictions, 1)) * 100
        total_requests = base_stats.get('total_requests', 0) or (base_stats.get('cache_hits', 0) + base_stats.get('cache_misses', 0))
        pattern_match_rate = (self.pattern_matches / max(total_requests, 1)) * 100
        
        return {
            **base_stats,
            "advanced_features": {
                "predictive_caching": {
                    "predictions_made": self.total_predictions,
                    "prediction_hits": self.prediction_hits,
                    "success_rate": f"{prediction_success_rate:.1f}%"
                },
                "pattern_matching": {
                    "pattern_matches": self.pattern_matches,
                    "match_rate": f"{pattern_match_rate:.1f}%"
                },
                "variation_database": {
                    "categories": len(set(self.question_variations.values())),
                    "total_variations": len(self.question_variations)
                }
            }
        }
    
    def clear_cache(self, pattern=None):
        """
        Clear cache with pattern support
        """
        self.cache_manager.clear(pattern)
        
        # Reset prediction stats
        self.prediction_hits = 0
        self.pattern_matches = 0
        self.total_predictions = 0
    
    def cache_db_query(self, query: str, results, ttl: int = 2400):
        """
        Cache database/vector search results - delegates to base cache manager
        """
        return self.cache_manager.cache_db_query(query, results, ttl)
    
    def clear(self, pattern=None):
        """
        Alias for clear_cache for compatibility
        """
        self.clear_cache(pattern)
    
    def get_db_query(self, query: str):
        """Get cached database query results - compatibility method"""
        return self.cache_manager.get_db_query(query)
    
    def invalidate_pattern(self, pattern):
        """
        Invalidate cache entries matching pattern
        """
        self.cache_manager.clear(pattern)
    
    def get_performance_summary(self):
        """
        Get performance summary for compatibility
        """
        stats = self.get_advanced_stats()
        return {
            "optimization_status": "Advanced caching with predictive capabilities + question variations",
            "cache_enabled": True,
            "advanced_features": stats.get("advanced_features", {}),
            "cache_entries": stats.get("total_entries", 0),
            "hit_rate": f"{stats.get('hit_rate_percent', 0):.1f}%"
        }

# Test function
def test_advanced_cache():
    """
    Test advanced cache features
    """
    print("🚀 TESTING ADVANCED CACHE")
    print("="*50)
    
    cache = AdvancedCacheService()
    
    # Test question variations
    test_questions = [
        "מה המחיר?",
        "כמה זה עולה?",
        "מה העלות?",
        "what's the price?"
    ]
    
    # Store first question
    cache.set(test_questions[0], {"answer": "המחיר הוא 100 שקל", "cached": True})
    
    # Test retrieval with variations
    for question in test_questions:
        result = cache.get(question)
        status = "✅ HIT" if result else "❌ MISS"
        print(f"{status}: {question}")
    
    stats = cache.get_advanced_stats()
    print(f"\n📊 Advanced Stats:")
    print(f"   Pattern matches: {stats['advanced_features']['pattern_matching']['pattern_matches']}")
    print(f"   Predictions made: {stats['advanced_features']['predictive_caching']['predictions_made']}")
    
    print("\n✅ Advanced cache test complete!")

if __name__ == "__main__":
    test_advanced_cache()