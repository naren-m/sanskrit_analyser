"""Tests for tiered cache coordinator."""

import os
import tempfile
from unittest.mock import AsyncMock, patch

import pytest

from sanskrit_analyzer.cache.tiered import (
    TieredCache,
    TieredCacheConfig,
    TieredCacheStats,
    TierStats,
)


class TestTierStats:
    """Tests for TierStats dataclass."""

    def test_default_values(self) -> None:
        """Test default statistics values."""
        stats = TierStats()
        assert stats.hits == 0
        assert stats.misses == 0
        assert stats.promotions == 0
        assert stats.errors == 0

    def test_hit_rate_empty(self) -> None:
        """Test hit rate with no accesses."""
        stats = TierStats()
        assert stats.hit_rate == 0.0

    def test_hit_rate_calculation(self) -> None:
        """Test hit rate calculation."""
        stats = TierStats(hits=75, misses=25)
        assert stats.hit_rate == 0.75


class TestTieredCacheStats:
    """Tests for TieredCacheStats dataclass."""

    def test_default_values(self) -> None:
        """Test default statistics values."""
        stats = TieredCacheStats()
        assert stats.total_requests == 0
        assert stats.memory.hits == 0
        assert stats.redis.hits == 0
        assert stats.sqlite.hits == 0

    def test_overall_hit_rate_empty(self) -> None:
        """Test overall hit rate with no requests."""
        stats = TieredCacheStats()
        assert stats.overall_hit_rate == 0.0

    def test_overall_hit_rate(self) -> None:
        """Test overall hit rate calculation."""
        stats = TieredCacheStats(total_requests=100)
        stats.memory.hits = 60
        stats.redis.hits = 20
        stats.sqlite.hits = 10
        # 90 hits out of 100 requests
        assert stats.overall_hit_rate == 0.9


class TestTieredCacheConfig:
    """Tests for TieredCacheConfig dataclass."""

    def test_defaults(self) -> None:
        """Test default configuration."""
        config = TieredCacheConfig()
        assert config.memory_enabled is True
        assert config.memory_max_size == 1000
        assert config.redis_enabled is False
        assert config.redis_url is None
        assert config.sqlite_enabled is True


class TestTieredCache:
    """Tests for TieredCache class."""

    @pytest.fixture
    def temp_db(self) -> str:
        """Create a temporary database file."""
        fd, path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        yield path
        if os.path.exists(path):
            os.unlink(path)

    @pytest.fixture
    def config(self, temp_db: str) -> TieredCacheConfig:
        """Create a test configuration."""
        return TieredCacheConfig(
            memory_enabled=True,
            memory_max_size=100,
            redis_enabled=False,
            sqlite_enabled=True,
            sqlite_path=temp_db,
        )

    @pytest.fixture
    def cache(self, config: TieredCacheConfig) -> TieredCache:
        """Create a cache instance."""
        return TieredCache(config)

    def test_init_with_defaults(self) -> None:
        """Test initialization with default config."""
        cache = TieredCache()
        status = cache.get_tier_status()
        assert status["memory"] is True
        assert status["redis"] is False
        assert status["sqlite"] is True

    def test_init_memory_only(self) -> None:
        """Test initialization with memory only."""
        config = TieredCacheConfig(
            memory_enabled=True,
            redis_enabled=False,
            sqlite_enabled=False,
        )
        cache = TieredCache(config)
        status = cache.get_tier_status()
        assert status["memory"] is True
        assert status["redis"] is False
        assert status["sqlite"] is False

    def test_make_key(self, cache: TieredCache) -> None:
        """Test cache key generation."""
        key1 = cache.make_key("gacchati", "PRODUCTION")
        key2 = cache.make_key("gacchati", "PRODUCTION")
        key3 = cache.make_key("gacchati", "ACADEMIC")

        assert key1 == key2
        assert key1 != key3
        assert len(key1) == 32

    @pytest.mark.asyncio
    async def test_set_and_get_memory(self, cache: TieredCache) -> None:
        """Test set and get with memory tier."""
        result = {"segments": [{"surface": "test"}]}
        key = cache.make_key("test", "PRODUCTION")

        await cache.set(key, "test", "test", "PRODUCTION", result)
        retrieved = await cache.get(key)

        assert retrieved == result
        assert cache.stats.memory.hits == 1

    @pytest.mark.asyncio
    async def test_get_miss(self, cache: TieredCache) -> None:
        """Test cache miss."""
        result = await cache.get("nonexistent")
        assert result is None
        assert cache.stats.total_requests == 1
        assert cache.stats.memory.misses == 1

    @pytest.mark.asyncio
    async def test_sqlite_promotion(self, config: TieredCacheConfig) -> None:
        """Test promotion from SQLite to memory."""
        cache = TieredCache(config)

        # Store directly in SQLite
        result = {"segments": [{"surface": "test"}]}
        key = cache.make_key("test", "PRODUCTION")
        cache._sqlite.set(key, "test", "test", "PRODUCTION", result)  # type: ignore

        # Clear memory to force SQLite hit
        cache._memory.clear()  # type: ignore

        # Get should hit SQLite and promote to memory
        retrieved = await cache.get(key)
        assert retrieved == result
        assert cache.stats.sqlite.hits == 1
        assert cache.stats.memory.promotions == 1

        # Second get should hit memory
        retrieved = await cache.get(key)
        assert retrieved == result
        assert cache.stats.memory.hits == 1

    @pytest.mark.asyncio
    async def test_delete(self, cache: TieredCache) -> None:
        """Test deleting from all tiers."""
        result = {"segments": []}
        key = cache.make_key("test", "PRODUCTION")

        await cache.set(key, "test", "test", "PRODUCTION", result)
        assert await cache.exists(key)

        deleted = await cache.delete(key)
        assert deleted is True
        assert not await cache.exists(key)

    @pytest.mark.asyncio
    async def test_exists(self, cache: TieredCache) -> None:
        """Test exists check."""
        key = cache.make_key("test", "PRODUCTION")

        assert not await cache.exists(key)

        await cache.set(key, "test", "test", "PRODUCTION", {})
        assert await cache.exists(key)

    @pytest.mark.asyncio
    async def test_clear_memory(self, cache: TieredCache) -> None:
        """Test clearing memory tier only."""
        result = {"segments": []}
        key = cache.make_key("test", "PRODUCTION")

        await cache.set(key, "test", "test", "PRODUCTION", result)

        await cache.clear_memory()

        # Memory should be empty, but SQLite should still have it
        assert cache._memory.get(key) is None  # type: ignore
        assert cache._sqlite.get(key) is not None  # type: ignore

    @pytest.mark.asyncio
    async def test_clear_all(self, cache: TieredCache) -> None:
        """Test clearing all tiers."""
        result = {"segments": []}
        key = cache.make_key("test", "PRODUCTION")

        await cache.set(key, "test", "test", "PRODUCTION", result)

        await cache.clear_all()

        assert not await cache.exists(key)

    @pytest.mark.asyncio
    async def test_health_check(self, cache: TieredCache) -> None:
        """Test health check."""
        health = await cache.health_check()

        assert health["memory"] is True
        assert health["redis"] is False
        assert health["sqlite"] is True

    @pytest.mark.asyncio
    async def test_stats_tracking(self, cache: TieredCache) -> None:
        """Test statistics tracking."""
        result = {"segments": []}
        key = cache.make_key("test", "PRODUCTION")

        # Set
        await cache.set(key, "test", "test", "PRODUCTION", result)

        # Hit
        await cache.get(key)

        # Miss
        await cache.get("nonexistent")

        stats = cache.stats
        assert stats.total_requests == 2
        assert stats.memory.hits == 1
        assert stats.memory.misses == 1

    @pytest.mark.asyncio
    async def test_redis_tier_mocked(self, temp_db: str) -> None:
        """Test Redis tier with mocked client."""
        config = TieredCacheConfig(
            memory_enabled=True,
            memory_max_size=100,
            redis_enabled=True,
            redis_url="redis://localhost:6379",
            sqlite_enabled=True,
            sqlite_path=temp_db,
        )
        cache = TieredCache(config)

        # Mock Redis client
        mock_redis = AsyncMock()
        mock_redis.get.return_value = None
        mock_redis.set.return_value = True
        mock_redis.exists.return_value = False
        mock_redis.delete.return_value = 1
        mock_redis.health_check.return_value = True
        cache._redis._client = mock_redis

        result = {"segments": []}
        key = cache.make_key("test", "PRODUCTION")

        # Set should store in all tiers
        await cache.set(key, "test", "test", "PRODUCTION", result)
        mock_redis.setex.assert_called()

        # Delete should remove from all tiers
        await cache.delete(key)
        mock_redis.delete.assert_called()

    @pytest.mark.asyncio
    async def test_redis_promotion(self, temp_db: str) -> None:
        """Test promotion from Redis to memory."""
        config = TieredCacheConfig(
            memory_enabled=True,
            memory_max_size=100,
            redis_enabled=True,
            redis_url="redis://localhost:6379",
            sqlite_enabled=False,
        )
        cache = TieredCache(config)

        # Mock the entire RedisCache get method
        result = {"segments": [{"surface": "test"}]}

        async def mock_get(key: str) -> dict:
            return result

        cache._redis.get = mock_get  # type: ignore

        # Clear memory
        cache._memory.clear()  # type: ignore

        key = cache.make_key("test", "PRODUCTION")

        # Get should hit Redis and promote to memory
        retrieved = await cache.get(key)
        assert retrieved == result
        assert cache.stats.redis.hits == 1
        assert cache.stats.memory.promotions == 1

    @pytest.mark.asyncio
    async def test_initialize_and_close(self, temp_db: str) -> None:
        """Test async initialize and close."""
        config = TieredCacheConfig(
            memory_enabled=True,
            redis_enabled=True,
            redis_url="redis://localhost:6379",
            sqlite_enabled=True,
            sqlite_path=temp_db,
        )
        cache = TieredCache(config)

        # Initialize should try to connect to Redis
        # (will fail without real Redis, but shouldn't raise)
        await cache.initialize()

        # Close should be safe
        await cache.close()

    @pytest.mark.asyncio
    async def test_no_tiers_enabled(self) -> None:
        """Test behavior with no tiers enabled."""
        config = TieredCacheConfig(
            memory_enabled=False,
            redis_enabled=False,
            sqlite_enabled=False,
        )
        cache = TieredCache(config)

        result = await cache.get("key")
        assert result is None

        # Set should not raise
        await cache.set("key", "test", "test", "PRODUCTION", {})

        # Still nothing
        result = await cache.get("key")
        assert result is None

    def test_get_tier_status(self, cache: TieredCache) -> None:
        """Test tier status reporting."""
        status = cache.get_tier_status()
        assert isinstance(status, dict)
        assert "memory" in status
        assert "redis" in status
        assert "sqlite" in status
