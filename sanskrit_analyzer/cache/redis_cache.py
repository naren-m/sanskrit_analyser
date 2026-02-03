"""Redis-based cache for distributed analysis caching."""

import json
import logging
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)

# Default TTL: 7 days in seconds
DEFAULT_TTL = 604800


@dataclass
class RedisCacheStats:
    """Statistics for Redis cache."""

    hits: int = 0
    misses: int = 0
    errors: int = 0
    connected: bool = False

    @property
    def hit_rate(self) -> float:
        """Calculate cache hit rate."""
        total = self.hits + self.misses
        if total == 0:
            return 0.0
        return self.hits / total


class RedisCache:
    """Redis-based distributed cache for analysis results.

    Provides a shared cache layer that can be used across multiple
    services or instances. Gracefully handles connection failures
    by returning None instead of raising exceptions.

    Example:
        cache = RedisCache("redis://localhost:6379")
        await cache.set("key123", result, ttl=3600)
        result = await cache.get("key123")
    """

    def __init__(
        self,
        redis_url: str | None = None,
        default_ttl: int = DEFAULT_TTL,
        key_prefix: str = "sanskrit:",
    ) -> None:
        """Initialize the Redis cache.

        Args:
            redis_url: Redis connection URL (e.g., redis://localhost:6379).
                       If None, cache is disabled.
            default_ttl: Default TTL in seconds (default 7 days).
            key_prefix: Prefix for all cache keys.
        """
        self._redis_url = redis_url
        self._default_ttl = default_ttl
        self._key_prefix = key_prefix
        self._client: Any | None = None
        self._stats = RedisCacheStats()
        self._enabled = redis_url is not None

    @property
    def enabled(self) -> bool:
        """Check if Redis cache is enabled."""
        return self._enabled

    @property
    def stats(self) -> RedisCacheStats:
        """Get cache statistics."""
        return self._stats

    async def connect(self) -> bool:
        """Establish connection to Redis.

        Returns:
            True if connection succeeded, False otherwise.
        """
        if not self._enabled:
            return False

        try:
            import redis.asyncio as aioredis

            self._client = aioredis.from_url(
                self._redis_url,  # type: ignore[arg-type]
                encoding="utf-8",
                decode_responses=True,
            )
            # Test connection
            await self._client.ping()
            self._stats.connected = True
            logger.info("Connected to Redis at %s", self._redis_url)
            return True
        except ImportError:
            logger.warning("Redis package not installed. Redis cache disabled.")
            self._enabled = False
            return False
        except Exception as e:
            logger.warning("Failed to connect to Redis: %s", e)
            self._stats.connected = False
            self._stats.errors += 1
            return False

    async def close(self) -> None:
        """Close the Redis connection."""
        if self._client is not None:
            try:
                await self._client.close()
            except Exception:
                pass
            self._client = None
            self._stats.connected = False

    def _make_key(self, key: str) -> str:
        """Create a prefixed cache key.

        Args:
            key: The base key.

        Returns:
            Prefixed key.
        """
        return f"{self._key_prefix}{key}"

    async def get(self, key: str) -> dict[str, Any] | None:
        """Get a value from the cache.

        Args:
            key: Cache key.

        Returns:
            Cached value as dictionary, or None if not found or error.
        """
        if not self._enabled or self._client is None:
            self._stats.misses += 1
            return None

        try:
            prefixed_key = self._make_key(key)
            value = await self._client.get(prefixed_key)

            if value is None:
                self._stats.misses += 1
                return None

            self._stats.hits += 1
            result: dict[str, Any] = json.loads(value)
            return result
        except Exception as e:
            logger.debug("Redis get error for key %s: %s", key, e)
            self._stats.errors += 1
            self._stats.misses += 1
            return None

    async def set(
        self,
        key: str,
        value: dict[str, Any],
        ttl: int | None = None,
    ) -> bool:
        """Store a value in the cache.

        Args:
            key: Cache key.
            value: Value to store (will be JSON serialized).
            ttl: Time-to-live in seconds. Uses default if not specified.

        Returns:
            True if stored successfully, False otherwise.
        """
        if not self._enabled or self._client is None:
            return False

        try:
            prefixed_key = self._make_key(key)
            json_value = json.dumps(value, ensure_ascii=False)
            expire = ttl if ttl is not None else self._default_ttl

            await self._client.setex(prefixed_key, expire, json_value)
            return True
        except Exception as e:
            logger.debug("Redis set error for key %s: %s", key, e)
            self._stats.errors += 1
            return False

    async def delete(self, key: str) -> bool:
        """Delete a value from the cache.

        Args:
            key: Cache key.

        Returns:
            True if deleted, False otherwise.
        """
        if not self._enabled or self._client is None:
            return False

        try:
            prefixed_key = self._make_key(key)
            result = await self._client.delete(prefixed_key)
            return bool(result)
        except Exception as e:
            logger.debug("Redis delete error for key %s: %s", key, e)
            self._stats.errors += 1
            return False

    async def exists(self, key: str) -> bool:
        """Check if a key exists in the cache.

        Args:
            key: Cache key.

        Returns:
            True if key exists, False otherwise.
        """
        if not self._enabled or self._client is None:
            return False

        try:
            prefixed_key = self._make_key(key)
            result = await self._client.exists(prefixed_key)
            return bool(result)
        except Exception as e:
            logger.debug("Redis exists error for key %s: %s", key, e)
            self._stats.errors += 1
            return False

    async def clear_prefix(self, prefix: str = "") -> int:
        """Clear all keys matching a prefix.

        Args:
            prefix: Additional prefix to match (combined with key_prefix).

        Returns:
            Number of keys deleted.
        """
        if not self._enabled or self._client is None:
            return 0

        try:
            pattern = f"{self._key_prefix}{prefix}*"
            deleted = 0
            async for key in self._client.scan_iter(match=pattern):
                await self._client.delete(key)
                deleted += 1
            return deleted
        except Exception as e:
            logger.debug("Redis clear error: %s", e)
            self._stats.errors += 1
            return 0

    async def health_check(self) -> bool:
        """Check if Redis is healthy.

        Returns:
            True if Redis is responding, False otherwise.
        """
        if not self._enabled or self._client is None:
            return False

        try:
            await self._client.ping()
            return True
        except Exception:
            return False

    async def get_ttl(self, key: str) -> int | None:
        """Get the TTL of a key.

        Args:
            key: Cache key.

        Returns:
            TTL in seconds, or None if key doesn't exist or error.
        """
        if not self._enabled or self._client is None:
            return None

        try:
            prefixed_key = self._make_key(key)
            ttl = await self._client.ttl(prefixed_key)
            return int(ttl) if ttl > 0 else None
        except Exception as e:
            logger.debug("Redis TTL error for key %s: %s", key, e)
            self._stats.errors += 1
            return None
