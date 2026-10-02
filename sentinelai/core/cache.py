"""
Small cache abstraction: in-memory by default, Redis when ``REDIS_URL`` is set.

Used for (a) research-agent result caching and (b) rate-limit counters, so a
multi-worker deployment can share state while a laptop needs nothing installed.
"""

from __future__ import annotations

import time
from typing import Any, Dict, Optional, Protocol

from sentinelai.core.config import settings
from sentinelai.core.logging import get_logger

logger = get_logger(__name__)


class Cache(Protocol):
    async def get(self, key: str) -> Optional[str]: ...
    async def set(self, key: str, value: str, ttl: int) -> None: ...
    async def incr(self, key: str, ttl: int) -> int: ...


class MemoryCache:
    def __init__(self, max_items: int = 5000):
        self._data: Dict[str, tuple[float, Any]] = {}
        self._max = max_items

    def _purge(self) -> None:
        now = time.monotonic()
        for k in [k for k, (exp, _) in self._data.items() if exp <= now]:
            del self._data[k]
        while len(self._data) > self._max:                    # bounded memory
            self._data.pop(next(iter(self._data)))

    async def get(self, key: str) -> Optional[str]:
        item = self._data.get(key)
        if item and item[0] > time.monotonic():
            return item[1]
        self._data.pop(key, None)
        return None

    async def set(self, key: str, value: str, ttl: int) -> None:
        self._data[key] = (time.monotonic() + ttl, value)
        if len(self._data) > self._max:
            self._purge()

    async def incr(self, key: str, ttl: int) -> int:
        item = self._data.get(key)
        if item and item[0] > time.monotonic():
            value = int(item[1]) + 1
            self._data[key] = (item[0], value)
            return value
        self._data[key] = (time.monotonic() + ttl, 1)
        if len(self._data) > self._max:
            self._purge()
        return 1


class RedisCache:
    def __init__(self, url: str):
        import redis.asyncio as redis
        self._r = redis.from_url(url, decode_responses=True)

    async def get(self, key: str) -> Optional[str]:
        return await self._r.get(key)

    async def set(self, key: str, value: str, ttl: int) -> None:
        await self._r.set(key, value, ex=ttl)

    async def incr(self, key: str, ttl: int) -> int:
        pipe = self._r.pipeline()
        pipe.incr(key)
        pipe.expire(key, ttl, nx=True)
        value, _ = await pipe.execute()
        return int(value)


_cache: Optional[Cache] = None


def get_cache() -> Cache:
    global _cache
    if _cache is None:
        url = settings.database.redis_url
        if url:
            try:
                _cache = RedisCache(url)
                logger.info("Using Redis cache")
            except Exception as exc:
                logger.warning("Redis unavailable (%s) - falling back to in-memory cache", exc)
        if _cache is None:
            _cache = MemoryCache()
    return _cache


def reset_cache() -> None:
    global _cache
    _cache = None
