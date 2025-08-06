import hashlib
import json
import time
import logging
from typing import Any, Optional, Dict, Tuple
from collections import OrderedDict

logger = logging.getLogger(__name__)

class IntelligentCacheManager:
    """
    Intelligent caching system for chatbot queries with TTL, size limits, and performance monitoring.
    Optimized for fast response times and reduced API calls.
    """
    
    def __init__(self, max_size: int = 500, default_ttl: int = 1800):
        """
        Initialize cache manager with performance-focused settings.
        
        Args:
            max_size: Maximum number of cache entries (reduced for performance)
            default_ttl: Default TTL in seconds (30 minutes)
        """
        self.max_size = max_size
        self.default_ttl = default_ttl
        
        # Cache storage: {key: {"data": value, "timestamp": time, "ttl": ttl, "access_count": int}}
        self._cache = OrderedDict()
        
        # Cache statistics
        self._stats = {
            "hits": 0,
            "misses": 0,
            "evictions": 0,
            "total_queries": 0,
            "last_cleanup": time.time()
        }
        
        logger.info(f"[CACHE] Initialized with max_size={max_size}, default_ttl={default_ttl}s")
    
    def _generate_cache_key(self, data: Dict[str, Any], prefix: str = "") -> str:
        """
        Generate a deterministic cache key from data.
        Optimized for speed.
        
        Args:
            data: Dictionary to hash
            prefix: Optional prefix for the key
            
        Returns:
            SHA256 hash of the data
        """
        # Fast string concatenation for common cases
        if isinstance(data, dict) and len(data) <= 3:
            key_parts = []
            for k, v in sorted(data.items()):
                key_parts.append(f"{k}:{str(v)[:100]}")  # Limit value length
            sorted_data = "|".join(key_parts)
        else:
            # Fallback to JSON for complex data
            sorted_data = json.dumps(data, sort_keys=True, ensure_ascii=False)[:200]
        
        hash_obj = hashlib.sha256(sorted_data.encode('utf-8'))
        key = hash_obj.hexdigest()[:12]  # Shorter hash for performance
        
        return f"{prefix}:{key}" if prefix else key
    
    def _is_expired(self, entry: Dict[str, Any]) -> bool:
        """Check if cache entry is expired."""
        return time.time() - entry["timestamp"] > entry["ttl"]
    
    def _cleanup_expired(self):
        """Remove expired entries from cache. Called infrequently for performance."""
        current_time = time.time()
        
        # Only cleanup every 10 minutes to avoid overhead
        if current_time - self._stats["last_cleanup"] < 600:
            return
            
        expired_keys = []
        for key, entry in list(self._cache.items()):
            if self._is_expired(entry):
                expired_keys.append(key)
        
        for key in expired_keys:
            del self._cache[key]
        
        if expired_keys:
            logger.debug(f"[CACHE] Cleaned up {len(expired_keys)} expired entries")
        
        self._stats["last_cleanup"] = current_time
    
    def _evict_lru(self):
        """Evict least recently used item."""
        if self._cache:
            evicted_key = next(iter(self._cache))
            del self._cache[evicted_key]
            self._stats["evictions"] += 1
            logger.debug(f"[CACHE] Evicted LRU key: {evicted_key}")
    
    def get(self, key: str) -> Optional[Any]:
        """
        Get value from cache with fast lookup.
        
        Args:
            key: Cache key
            
        Returns:
            Cached value or None if not found/expired
        """
        self._stats["total_queries"] += 1
        
        if key not in self._cache:
            self._stats["misses"] += 1
            return None
        
        entry = self._cache[key]
        
        # Quick expiration check
        if self._is_expired(entry):
            del self._cache[key]
            self._stats["misses"] += 1
            return None
        
        # Move to end (mark as recently used) - fast operation
        self._cache.move_to_end(key)
        entry["access_count"] += 1
        
        self._stats["hits"] += 1
        return entry["data"]
    
    def set(self, key: str, value: Any, ttl: Optional[int] = None):
        """
        Set value in cache with performance optimization.
        
        Args:
            key: Cache key
            value: Value to cache
            ttl: TTL in seconds, uses default if None
        """
        # Evict LRU if at capacity (no expensive cleanup every time)
        while len(self._cache) >= self.max_size:
            self._evict_lru()
        
        # Store entry
        entry = {
            "data": value,
            "timestamp": time.time(),
            "ttl": ttl or self.default_ttl,
            "access_count": 1
        }
        
        self._cache[key] = entry
        
        # Cleanup expired entries occasionally
        if len(self._cache) % 50 == 0:  # Every 50 entries
            self._cleanup_expired()
    
    def cache_openai_response(self, question: str, context: str, session_data: Dict[str, Any], response: str, ttl: int = 1200):
        """
        Cache OpenAI response with intelligent key generation.
        Optimized for fast key generation.
        
        Args:
            question: User question
            context: Context used for generation
            session_data: Relevant session data for key generation
            response: OpenAI response to cache
            ttl: TTL in seconds (20 minutes default)
        """
        # Fast cache key generation
        cache_data = {
            "q": question.lower().strip()[:100],  # Truncate for speed
            "ctx": context[:200] if context else "",  # Limit context size
            "lang": session_data.get("language", "auto"),
            "greeted": session_data.get("greeted", False)
        }
        
        key = self._generate_cache_key(cache_data, "ai")
        self.set(key, response, ttl)
        
        return key
    
    def get_openai_response(self, question: str, context: str, session_data: Dict[str, Any]) -> Optional[str]:
        """
        Get cached OpenAI response with fast lookup.
        
        Args:
            question: User question
            context: Context used for generation
            session_data: Relevant session data
            
        Returns:
            Cached response or None
        """
        cache_data = {
            "q": question.lower().strip()[:100],
            "ctx": context[:200] if context else "",
            "lang": session_data.get("language", "auto"),
            "greeted": session_data.get("greeted", False)
        }
        
        key = self._generate_cache_key(cache_data, "ai")
        return self.get(key)
    
    def cache_db_query(self, query: str, results: Any, ttl: int = 2400):
        """
        Cache database/vector search results with fast key generation.
        
        Args:
            query: Search query
            results: Query results
            ttl: TTL in seconds (40 minutes default)
        """
        # Simple key for database queries
        cache_data = {"query": query.lower().strip()[:100]}
        key = self._generate_cache_key(cache_data, "db")
        self.set(key, results, ttl)
        
        return key
    
    def get_db_query(self, query: str) -> Optional[Any]:
        """
        Get cached database query results with fast lookup.
        
        Args:
            query: Search query
            
        Returns:
            Cached results or None
        """
        cache_data = {"query": query.lower().strip()[:100]}
        key = self._generate_cache_key(cache_data, "db")
        return self.get(key)
    
    def invalidate_pattern(self, pattern: str):
        """
        Invalidate cache entries matching a pattern.
        
        Args:
            pattern: Pattern to match (e.g., "ai:", "db:")
        """
        keys_to_remove = [key for key in self._cache.keys() if key.startswith(pattern)]
        
        for key in keys_to_remove:
            del self._cache[key]
        
        if keys_to_remove:
            logger.info(f"[CACHE] Invalidated {len(keys_to_remove)} entries matching pattern: {pattern}")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        total_queries = self._stats["total_queries"]
        hit_rate = (self._stats["hits"] / total_queries * 100) if total_queries > 0 else 0
        
        return {
            "total_entries": len(self._cache),
            "max_size": self.max_size,
            "total_queries": total_queries,
            "cache_hits": self._stats["hits"],
            "cache_misses": self._stats["misses"],
            "hit_rate_percent": round(hit_rate, 2),
            "evictions": self._stats["evictions"],
            "last_cleanup": self._stats["last_cleanup"]
        }
    
    def clear(self):
        """Clear all cache entries."""
        self._cache.clear()
        self._stats = {
            "hits": 0,
            "misses": 0,
            "evictions": 0,
            "total_queries": 0,
            "last_cleanup": time.time()
        }
        logger.info("[CACHE] Cache cleared")
    
    def get_performance_summary(self):
        """Get performance-focused cache summary."""
        stats = self.get_stats()
        return {
            "hit_rate": stats["hit_rate_percent"],
            "total_entries": stats["total_entries"],
            "efficiency": "High" if stats["hit_rate_percent"] > 60 else "Medium" if stats["hit_rate_percent"] > 30 else "Low"
        }