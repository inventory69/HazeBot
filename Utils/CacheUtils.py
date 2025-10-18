import asyncio
import json
import os
from typing import Any, Callable, Dict, Optional, TypeVar
from functools import wraps
import time
from Utils.Logger import Logger  # ← Hinzugefügt

F = TypeVar("F", bound=Callable[..., Any])


# === In-memory cache with TTL ===
class Cache:
    def __init__(self):
        self._cache: Dict[str, Dict[str, Any]] = {}

    def get(self, key: str) -> Optional[Any]:
        if key in self._cache:
            entry = self._cache[key]
            if time.time() < entry["expires"]:
                return entry["value"]
            else:
                del self._cache[key]
        return None

    def set(self, key: str, value: Any, ttl_seconds: int) -> None:
        self._cache[key] = {"value": value, "expires": time.time() + ttl_seconds}

    def clear(self, key: str) -> None:
        if key in self._cache:
            del self._cache[key]

    async def get_or_set(self, key: str, fetch_func: Callable[[], Any], ttl: int) -> Any:
        """
        Get from cache or set by calling fetch_func and cache the result.
        """
        cached = self.get(key)
        if cached is not None:
            return cached

        result = await fetch_func()
        self.set(key, result, ttl)
        return result


# Global cache instance
cache_instance = Cache()


def cache(ttl_seconds: int) -> Callable[[F], F]:
    """
    Decorator for caching function results in memory with TTL.
    Usage: @cache(ttl_seconds=30)
    """

    def decorator(func: F) -> F:
        @wraps(func)
        async def async_wrapper(*args, **kwargs) -> Any:
            # Create a cache key from function name and args
            key = f"{func.__name__}:{str(args)}:{str(kwargs)}"
            cached = cache_instance.get(key)
            if cached is not None:
                return cached

            result = await func(*args, **kwargs)
            cache_instance.set(key, result, ttl_seconds)
            return result

        @wraps(func)
        def sync_wrapper(*args, **kwargs) -> Any:
            # Create a cache key from function name and args
            key = f"{func.__name__}:{str(args)}:{str(kwargs)}"
            cached = cache_instance.get(key)
            if cached is not None:
                return cached

            result = func(*args, **kwargs)
            cache_instance.set(key, result, ttl_seconds)
            return result

        if asyncio.iscoroutinefunction(func):
            return async_wrapper  # type: ignore
        else:
            return sync_wrapper  # type: ignore

    return decorator


# === File-based cache for expensive operations ===
class FileCache:
    def __init__(self, cache_dir: str = "Cache"):
        self.cache_dir = cache_dir
        os.makedirs(cache_dir, exist_ok=True)

    def _get_cache_path(self, key: str) -> str:
        return os.path.join(self.cache_dir, f"{key}.json")

    def get(self, key: str) -> Optional[Any]:
        path = self._get_cache_path(key)
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if time.time() < data["expires"]:
                        return data["value"]
                    else:
                        os.remove(path)
            except (json.JSONDecodeError, KeyError):
                os.remove(path)
        return None

    def set(self, key: str, value: Any, ttl_seconds: int) -> None:
        path = self._get_cache_path(key)
        data = {"value": value, "expires": time.time() + ttl_seconds}
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    def clear(self, key: str) -> None:
        path = self._get_cache_path(key)
        if os.path.exists(path):
            os.remove(path)

    async def get_or_set(self, key: str, fetch_func: Callable[[], Any], ttl: int) -> Any:
        """
        Get from cache or set by calling fetch_func and cache the result.
        """
        cached = self.get(key)
        if cached is not None:
            return cached

        result = await fetch_func()
        self.set(key, result, ttl)
        return result


# Global file cache instance
file_cache = FileCache()


def file_cache_decorator(ttl_seconds: int) -> Callable[[F], F]:
    """
    Decorator for caching function results to file with TTL.
    Usage: @file_cache(ttl_seconds=3600)
    """

    def decorator(func: F) -> F:
        @wraps(func)
        async def async_wrapper(*args, **kwargs) -> Any:
            # Create a cache key from function name and args
            key = f"{func.__name__}:{str(args)}:{str(kwargs)}"
            cached = file_cache.get(key)
            if cached is not None:
                return cached

            result = await func(*args, **kwargs)
            file_cache.set(key, result, ttl_seconds)
            return result

        @wraps(func)
        def sync_wrapper(*args, **kwargs) -> Any:
            # Create a cache key from function name and args
            key = f"{func.__name__}:{str(args)}:{str(kwargs)}"
            cached = file_cache.get(key)
            if cached is not None:
                return cached

            result = func(*args, **kwargs)
            file_cache.set(key, result, ttl_seconds)
            return result

        if asyncio.iscoroutinefunction(func):
            return async_wrapper  # type: ignore
        else:
            return sync_wrapper  # type: ignore

    return decorator


def invalidate_cache(func):
    """Invalidate cache for a specific function."""
    cache_key = f"{func.__module__}.{func.__name__}"
    if cache_key in cache_instance._cache:
        del cache_instance._cache[cache_key]
        Logger.info(f"Cache invalidated for {cache_key}")
