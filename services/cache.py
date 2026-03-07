# fx/services/cache.py
import json
import pickle
from typing import Any, Optional, Dict
from datetime import timedelta
import logging
import redis
from redis.exceptions import RedisError

from config.settings import settings

logger = logging.getLogger(__name__)


class CacheService:
    """
    Redis-based caching service
    """
    
    def __init__(self):
        self.redis_client = None
        self._connect()
    
    def _connect(self):
        """Connect to Redis"""
        try:
            self.redis_client = redis.from_url(
                settings.REDIS_URL,
                decode_responses=False,  # For binary data
                socket_connect_timeout=2,
                socket_timeout=5,
                retry_on_timeout=True
            )
            # Test connection
            self.redis_client.ping()
            logger.info("Connected to Redis")
        except Exception as e:
            logger.error(f"Failed to connect to Redis: {e}")
            self.redis_client = None
    
    def _ensure_connection(self):
        """Ensure Redis connection is alive"""
        if not self.redis_client:
            self._connect()
            if not self.redis_client:
                return False
        return True
    
    def set(self, key: str, value: Any, ttl: Optional[timedelta] = None) -> bool:
        """Set a value in cache"""
        if not self._ensure_connection():
            return False
        
        try:
            # Serialize value
            if isinstance(value, (dict, list)):
                data = json.dumps(value)
            else:
                data = pickle.dumps(value)
            
            # Set with TTL
            if ttl:
                self.redis_client.setex(key, ttl, data)
            else:
                self.redis_client.set(key, data)
            
            return True
        except RedisError as e:
            logger.error(f"Redis set error: {e}")
            return False
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get a value from cache"""
        if not self._ensure_connection():
            return default
        
        try:
            data = self.redis_client.get(key)
            if not data:
                return default
            
            # Try JSON first
            try:
                return json.loads(data)
            except (json.JSONDecodeError, TypeError):
                pass
            
            # Try pickle
            try:
                return pickle.loads(data)
            except:
                return data.decode() if isinstance(data, bytes) else data
                
        except RedisError as e:
            logger.error(f"Redis get error: {e}")
            return default
    
    def delete(self, key: str) -> bool:
        """Delete a key from cache"""
        if not self._ensure_connection():
            return False
        
        try:
            self.redis_client.delete(key)
            return True
        except RedisError as e:
            logger.error(f"Redis delete error: {e}")
            return False
    
    def exists(self, key: str) -> bool:
        """Check if key exists"""
        if not self._ensure_connection():
            return False
        
        try:
            return self.redis_client.exists(key) > 0
        except RedisError as e:
            logger.error(f"Redis exists error: {e}")
            return False
    
    def increment(self, key: str, amount: int = 1) -> Optional[int]:
        """Increment a counter"""
        if not self._ensure_connection():
            return None
        
        try:
            return self.redis_client.incr(key, amount)
        except RedisError as e:
            logger.error(f"Redis increment error: {e}")
            return None
    
    def expire(self, key: str, ttl: timedelta) -> bool:
        """Set expiration on a key"""
        if not self._ensure_connection():
            return False
        
        try:
            return self.redis_client.expire(key, int(ttl.total_seconds()))
        except RedisError as e:
            logger.error(f"Redis expire error: {e}")
            return False
    
    def get_or_set(self, key: str, func, ttl: Optional[timedelta] = None) -> Any:
        """Get from cache or compute and store"""
        # Try cache first
        value = self.get(key)
        if value is not None:
            return value
        
        # Compute value
        value = func()
        if value is not None:
            self.set(key, value, ttl)
        
        return value
    
    def clear_pattern(self, pattern: str) -> int:
        """Clear all keys matching pattern"""
        if not self._ensure_connection():
            return 0
        
        try:
            keys = self.redis_client.keys(pattern)
            if keys:
                return self.redis_client.delete(*keys)
            return 0
        except RedisError as e:
            logger.error(f"Redis clear pattern error: {e}")
            return 0
    
    def get_stats(self) -> Dict[str, Any]:
        """Get Redis stats"""
        if not self._ensure_connection():
            return {'status': 'disconnected'}
        
        try:
            info = self.redis_client.info()
            return {
                'status': 'connected',
                'used_memory': info.get('used_memory_human', 'unknown'),
                'connected_clients': info.get('connected_clients', 0),
                'total_commands_processed': info.get('total_commands_processed', 0),
                'keyspace_hits': info.get('keyspace_hits', 0),
                'keyspace_misses': info.get('keyspace_misses', 0),
                'uptime_days': info.get('uptime_in_days', 0)
            }
        except Exception as e:
            return {'status': 'error', 'error': str(e)}


# Cache key constants
class CacheKeys:
    """Cache key constants"""
    
    # User data
    USER_PREFIX = "user:"
    USER_SETTINGS_PREFIX = "user:settings:"
    USER_STATS_PREFIX = "user:stats:"
    
    # Price data
    PRICE_PREFIX = "price:"
    
    # Rate limiting
    RATE_LIMIT_PREFIX = "ratelimit:"
    
    # Session data
    SESSION_PREFIX = "session:"
    
    # Trade data
    TRADE_PREFIX = "trade:"
    
    @staticmethod
    def user(user_id: int) -> str:
        return f"{CacheKeys.USER_PREFIX}{user_id}"
    
    @staticmethod
    def user_settings(user_id: int) -> str:
        return f"{CacheKeys.USER_SETTINGS_PREFIX}{user_id}"
    
    @staticmethod
    def user_stats(user_id: int) -> str:
        return f"{CacheKeys.USER_STATS_PREFIX}{user_id}"
    
    @staticmethod
    def price(symbol: str) -> str:
        return f"{CacheKeys.PRICE_PREFIX}{symbol}"
    
    @staticmethod
    def rate_limit(user_id: int, action: str) -> str:
        return f"{CacheKeys.RATE_LIMIT_PREFIX}{user_id}:{action}"
    
    @staticmethod
    def session(session_id: str) -> str:
        return f"{CacheKeys.SESSION_PREFIX}{session_id}"
    
    @staticmethod
    def trade(trade_uuid: str) -> str:
        return f"{CacheKeys.TRADE_PREFIX}{trade_uuid}"