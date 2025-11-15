"""
API Cache System for HazeBot
Simple in-memory cache with TTL (Time-To-Live) and invalidation support
Similar to Redis but without external dependencies
"""

import time
from functools import wraps
from typing import Any, Callable, Optional


class APICache:
    """Simple in-memory cache with TTL support"""

    def __init__(self):
        self._cache = {}  # {key: {value, expires_at, created_at}}
        self._stats = {
            "hits": 0,
            "misses": 0,
            "sets": 0,
            "invalidations": 0,
        }

    def get(self, key: str) -> Optional[Any]:
        """Get value from cache if not expired"""
        if key not in self._cache:
            self._stats["misses"] += 1
            return None

        entry = self._cache[key]

        # Check if expired
        if entry["expires_at"] and time.time() > entry["expires_at"]:
            del self._cache[key]
            self._stats["misses"] += 1
            return None

        self._stats["hits"] += 1
        return entry["value"]

    def set(self, key: str, value: Any, ttl: int = 300) -> None:
        """
        Set value in cache with TTL (Time-To-Live) in seconds
        Default: 5 minutes (300 seconds)
        """
        expires_at = time.time() + ttl if ttl > 0 else None

        self._cache[key] = {
            "value": value,
            "expires_at": expires_at,
            "created_at": time.time(),
        }
        self._stats["sets"] += 1

    def delete(self, key: str) -> bool:
        """Delete a specific key from cache"""
        if key in self._cache:
            del self._cache[key]
            self._stats["invalidations"] += 1
            return True
        return False

    def invalidate_pattern(self, pattern: str) -> int:
        """
        Invalidate all keys matching pattern (simple contains match)
        Returns number of keys invalidated
        """
        count = 0
        keys_to_delete = [k for k in self._cache.keys() if pattern in k]

        for key in keys_to_delete:
            del self._cache[key]
            count += 1

        self._stats["invalidations"] += count
        return count

    def clear(self) -> None:
        """Clear entire cache"""
        count = len(self._cache)
        self._cache.clear()
        self._stats["invalidations"] += count

    def cleanup_expired(self) -> int:
        """Remove all expired entries, return count of removed entries"""
        current_time = time.time()
        expired_keys = [
            key for key, entry in self._cache.items() if entry["expires_at"] and current_time > entry["expires_at"]
        ]

        for key in expired_keys:
            del self._cache[key]

        return len(expired_keys)

    def get_stats(self) -> dict:
        """Get cache statistics"""
        total_requests = self._stats["hits"] + self._stats["misses"]
        hit_rate = (self._stats["hits"] / total_requests * 100) if total_requests > 0 else 0

        return {
            **self._stats,
            "total_requests": total_requests,
            "hit_rate": round(hit_rate, 2),
            "cache_size": len(self._cache),
        }

    def get_all_keys(self) -> list:
        """Get all cache keys (for debugging)"""
        return list(self._cache.keys())


# Global cache instance
cache = APICache()


def cached(ttl: int = 300, key_prefix: str = "", invalidate_on: list = None):
    """
    Decorator to cache function results

    Args:
        ttl: Time-To-Live in seconds (default: 5 minutes)
        key_prefix: Prefix for cache key (default: function name)
        invalidate_on: List of patterns that should invalidate this cache

    Example:
        @cached(ttl=60, key_prefix="hazehub")
        def get_latest_memes():
            return expensive_operation()
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Build cache key from function name and arguments
            prefix = key_prefix or func.__name__

            # Create a unique key based on args/kwargs
            # Skip 'self' for class methods
            cache_args = args[1:] if args and hasattr(args[0], func.__name__) else args

            # Convert args/kwargs to string for key
            args_str = "_".join(str(arg) for arg in cache_args)
            kwargs_str = "_".join(f"{k}={v}" for k, v in sorted(kwargs.items()))

            cache_key = f"{prefix}:{args_str}:{kwargs_str}".strip(":")

            # Try to get from cache
            cached_value = cache.get(cache_key)
            if cached_value is not None:
                return cached_value

            # Execute function and cache result
            result = func(*args, **kwargs)
            cache.set(cache_key, result, ttl=ttl)

            return result

        return wrapper

    return decorator


def invalidate_cache(pattern: str) -> int:
    """Invalidate all cache entries matching pattern"""
    return cache.invalidate_pattern(pattern)


def get_cache_stats() -> dict:
    """Get cache statistics"""
    return cache.get_stats()


def clear_cache() -> None:
    """Clear entire cache"""
    cache.clear()


# Periodic cleanup (call this from a background thread if needed)
def cleanup_expired_cache() -> int:
    """Remove expired cache entries"""
    return cache.cleanup_expired()
