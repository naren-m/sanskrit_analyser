"""Tiered cache coordinator with Memory -> Redis -> SQLite fallback."""

import logging
from dataclasses import dataclass, field
from typing import Any

from sanskrit_analyzer.cache.memory import LRUCache
from sanskrit_analyzer.cache.redis_cache import RedisCache
from sanskrit_analyzer.cache.sqlite_corpus import SQLiteCorpus

logger = logging.getLogger(__name__)


@dataclass
class TieredCacheConfig:
    """Configuration for the tiered cache."""

    # Memory tier
    memory_enabled: bool = True
    memory_max_size: int = 1000

    # Redis tier
    redis_enabled: bool = False
    redis_url: str | None = None
    redis_ttl: int = 604800  # 7 days
    redis_key_prefix: str = "sanskrit:"

    # SQLite tier
    sqlite_enabled: bool = True
    sqlite_path: str | None = None


@dataclass
class TierStats:
    """Statistics for a single cache tier."""

    hits: int = 0
    misses: int = 0
    promotions: int = 0
    errors: int = 0

    @property
    def hit_rate(self) -> float:
        """Calculate hit rate."""
        total = self.hits + self.misses
        if total == 0:
            return 0.0
        return self.hits / total


@dataclass
class TieredCacheStats:
    """Statistics for all cache tiers."""

    memory: TierStats = field(default_factory=TierStats)
    redis: TierStats = field(default_factory=TierStats)
    sqlite: TierStats = field(default_factory=TierStats)
    total_requests: int = 0

    @property
    def overall_hit_rate(self) -> float:
        """Calculate overall hit rate across all tiers."""
        total_hits = self.memory.hits + self.redis.hits + self.sqlite.hits
        if self.total_requests == 0:
            return 0.0
        return total_hits / self.total_requests


class TieredCache:
    """Tiered cache with Memory -> Redis -> SQLite fallback.

    Checks caches in order (fastest to slowest):
    1. Memory (LRU cache)
    2. Redis (distributed cache)
    3. SQLite (persistent corpus)

    On cache hit, promotes the value to faster tiers.
    On set, stores in all enabled tiers.

    Example:
        config = TieredCacheConfig(redis_url="redis://localhost:6379")
        cache = TieredCache(config)
        await cache.initialize()

        await cache.set("key", "original", "normalized", "PRODUCTION", result)
        result = await cache.get("key")
    """

    def __init__(self, config: TieredCacheConfig | None = None) -> None:
        """Initialize the tiered cache.

        Args:
            config: Cache configuration. Uses defaults if not provided.
        """
        self._config = config or TieredCacheConfig()
        self._stats = TieredCacheStats()

        # Initialize memory tier
        self._memory: LRUCache | None = None
        if self._config.memory_enabled:
            self._memory = LRUCache(max_size=self._config.memory_max_size)

        # Initialize Redis tier
        self._redis: RedisCache | None = None
        if self._config.redis_enabled and self._config.redis_url:
            self._redis = RedisCache(
                redis_url=self._config.redis_url,
                default_ttl=self._config.redis_ttl,
                key_prefix=self._config.redis_key_prefix,
            )

        # Initialize SQLite tier
        self._sqlite: SQLiteCorpus | None = None
        if self._config.sqlite_enabled:
            self._sqlite = SQLiteCorpus(db_path=self._config.sqlite_path)

    @property
    def stats(self) -> TieredCacheStats:
        """Get cache statistics."""
        return self._stats

    async def initialize(self) -> None:
        """Initialize async components (Redis connection)."""
        if self._redis is not None:
            connected = await self._redis.connect()
            if not connected:
                logger.warning("Redis connection failed, disabling Redis tier")
                self._redis = None

    async def close(self) -> None:
        """Close all connections."""
        if self._redis is not None:
            await self._redis.close()
        if self._sqlite is not None:
            self._sqlite.close()

    async def get(self, key: str) -> dict[str, Any] | None:
        """Get a value from the cache.

        Checks tiers in order: Memory -> Redis -> SQLite.
        Promotes found values to faster tiers.

        Args:
            key: Cache key.

        Returns:
            Cached value or None if not found.
        """
        self._stats.total_requests += 1

        # Try memory tier
        if self._memory is not None:
            mem_value = self._memory.get(key)
            if mem_value is not None:
                self._stats.memory.hits += 1
                result: dict[str, Any] = mem_value
                return result
            self._stats.memory.misses += 1

        # Try Redis tier
        if self._redis is not None:
            value = await self._redis.get(key)
            if value is not None:
                self._stats.redis.hits += 1
                # Promote to memory
                if self._memory is not None:
                    self._memory.set(key, value)
                    self._stats.memory.promotions += 1
                return value
            self._stats.redis.misses += 1

        # Try SQLite tier
        if self._sqlite is not None:
            entry = self._sqlite.get(key)
            if entry is not None:
                self._stats.sqlite.hits += 1
                value = entry.get_result()
                # Promote to faster tiers
                if self._memory is not None:
                    self._memory.set(key, value)
                    self._stats.memory.promotions += 1
                if self._redis is not None:
                    await self._redis.set(key, value)
                    self._stats.redis.promotions += 1
                return value
            self._stats.sqlite.misses += 1

        return None

    async def set(
        self,
        key: str,
        original_text: str,
        normalized_slp1: str,
        mode: str,
        result: dict[str, Any],
    ) -> None:
        """Store a value in all enabled cache tiers.

        Args:
            key: Cache key.
            original_text: Original input text.
            normalized_slp1: Normalized SLP1 text.
            mode: Analysis mode.
            result: Analysis result dictionary.
        """
        # Store in memory tier
        if self._memory is not None:
            self._memory.set(key, result)

        # Store in Redis tier
        if self._redis is not None:
            try:
                await self._redis.set(key, result)
            except Exception as e:
                logger.debug("Redis set error: %s", e)
                self._stats.redis.errors += 1

        # Store in SQLite tier
        if self._sqlite is not None:
            try:
                self._sqlite.set(key, original_text, normalized_slp1, mode, result)
            except Exception as e:
                logger.debug("SQLite set error: %s", e)
                self._stats.sqlite.errors += 1

    async def delete(self, key: str) -> bool:
        """Delete a value from all cache tiers.

        Args:
            key: Cache key.

        Returns:
            True if deleted from at least one tier.
        """
        deleted = False

        if self._memory is not None:
            if self._memory.delete(key):
                deleted = True

        if self._redis is not None:
            if await self._redis.delete(key):
                deleted = True

        if self._sqlite is not None:
            if self._sqlite.delete(key):
                deleted = True

        return deleted

    async def exists(self, key: str) -> bool:
        """Check if a key exists in any cache tier.

        Args:
            key: Cache key.

        Returns:
            True if key exists in any tier.
        """
        if self._memory is not None and self._memory.contains(key):
            return True

        if self._redis is not None and await self._redis.exists(key):
            return True

        if self._sqlite is not None and self._sqlite.get(key) is not None:
            return True

        return False

    async def clear_memory(self) -> None:
        """Clear memory tier only."""
        if self._memory is not None:
            self._memory.clear()

    async def clear_all(self) -> None:
        """Clear all cache tiers."""
        if self._memory is not None:
            self._memory.clear()

        if self._redis is not None:
            await self._redis.clear_prefix()

        if self._sqlite is not None:
            self._sqlite.clear()

    def make_key(self, text: str, mode: str = "PRODUCTION") -> str:
        """Generate a cache key from text and mode.

        Args:
            text: Normalized SLP1 text.
            mode: Analysis mode.

        Returns:
            Cache key.
        """
        if self._memory is not None:
            return self._memory.make_key(text, mode)
        # Fallback key generation
        import hashlib

        content = f"{mode}:{text}"
        return hashlib.sha256(content.encode("utf-8")).hexdigest()[:32]

    def get_tier_status(self) -> dict[str, bool]:
        """Get enabled status of each tier.

        Returns:
            Dictionary with tier enabled status.
        """
        return {
            "memory": self._memory is not None,
            "redis": self._redis is not None,
            "sqlite": self._sqlite is not None,
        }

    async def health_check(self) -> dict[str, bool]:
        """Check health of all tiers.

        Returns:
            Dictionary with tier health status.
        """
        health: dict[str, bool] = {}

        health["memory"] = self._memory is not None

        if self._redis is not None:
            health["redis"] = await self._redis.health_check()
        else:
            health["redis"] = False

        if self._sqlite is not None:
            try:
                self._sqlite.count()
                health["sqlite"] = True
            except Exception:
                health["sqlite"] = False
        else:
            health["sqlite"] = False

        return health
