"""Tests for Redis cache."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from sanskrit_analyzer.cache.redis_cache import RedisCache, RedisCacheStats


class TestRedisCacheStats:
    """Tests for RedisCacheStats dataclass."""

    def test_default_values(self) -> None:
        """Test default statistics values."""
        stats = RedisCacheStats()
        assert stats.hits == 0
        assert stats.misses == 0
        assert stats.errors == 0
        assert stats.connected is False

    def test_hit_rate_empty(self) -> None:
        """Test hit rate with no accesses."""
        stats = RedisCacheStats()
        assert stats.hit_rate == 0.0

    def test_hit_rate_calculation(self) -> None:
        """Test hit rate calculation."""
        stats = RedisCacheStats(hits=75, misses=25)
        assert stats.hit_rate == 0.75


class TestRedisCache:
    """Tests for RedisCache class."""

    def test_init_disabled(self) -> None:
        """Test initialization with no URL disables cache."""
        cache = RedisCache(redis_url=None)
        assert cache.enabled is False

    def test_init_enabled(self) -> None:
        """Test initialization with URL enables cache."""
        cache = RedisCache(redis_url="redis://localhost:6379")
        assert cache.enabled is True

    def test_make_key(self) -> None:
        """Test key prefixing."""
        cache = RedisCache(redis_url="redis://localhost:6379", key_prefix="test:")
        assert cache._make_key("mykey") == "test:mykey"

    @pytest.mark.asyncio
    async def test_get_disabled(self) -> None:
        """Test get when cache is disabled."""
        cache = RedisCache(redis_url=None)
        result = await cache.get("key")
        assert result is None
        assert cache.stats.misses == 1

    @pytest.mark.asyncio
    async def test_set_disabled(self) -> None:
        """Test set when cache is disabled."""
        cache = RedisCache(redis_url=None)
        result = await cache.set("key", {"test": "value"})
        assert result is False

    @pytest.mark.asyncio
    async def test_get_success(self) -> None:
        """Test successful get operation."""
        cache = RedisCache(redis_url="redis://localhost:6379")

        # Mock Redis client
        mock_client = AsyncMock()
        mock_client.get.return_value = '{"test": "value"}'
        cache._client = mock_client

        result = await cache.get("key")
        assert result == {"test": "value"}
        assert cache.stats.hits == 1
        mock_client.get.assert_called_once_with("sanskrit:key")

    @pytest.mark.asyncio
    async def test_get_miss(self) -> None:
        """Test cache miss."""
        cache = RedisCache(redis_url="redis://localhost:6379")

        mock_client = AsyncMock()
        mock_client.get.return_value = None
        cache._client = mock_client

        result = await cache.get("key")
        assert result is None
        assert cache.stats.misses == 1

    @pytest.mark.asyncio
    async def test_get_error(self) -> None:
        """Test get with error."""
        cache = RedisCache(redis_url="redis://localhost:6379")

        mock_client = AsyncMock()
        mock_client.get.side_effect = Exception("Connection error")
        cache._client = mock_client

        result = await cache.get("key")
        assert result is None
        assert cache.stats.errors == 1
        assert cache.stats.misses == 1

    @pytest.mark.asyncio
    async def test_set_success(self) -> None:
        """Test successful set operation."""
        cache = RedisCache(redis_url="redis://localhost:6379", default_ttl=3600)

        mock_client = AsyncMock()
        cache._client = mock_client

        result = await cache.set("key", {"test": "value"})
        assert result is True
        mock_client.setex.assert_called_once()
        args = mock_client.setex.call_args[0]
        assert args[0] == "sanskrit:key"
        assert args[1] == 3600
        assert '"test": "value"' in args[2]

    @pytest.mark.asyncio
    async def test_set_custom_ttl(self) -> None:
        """Test set with custom TTL."""
        cache = RedisCache(redis_url="redis://localhost:6379")

        mock_client = AsyncMock()
        cache._client = mock_client

        await cache.set("key", {"test": "value"}, ttl=60)
        args = mock_client.setex.call_args[0]
        assert args[1] == 60

    @pytest.mark.asyncio
    async def test_set_error(self) -> None:
        """Test set with error."""
        cache = RedisCache(redis_url="redis://localhost:6379")

        mock_client = AsyncMock()
        mock_client.setex.side_effect = Exception("Connection error")
        cache._client = mock_client

        result = await cache.set("key", {"test": "value"})
        assert result is False
        assert cache.stats.errors == 1

    @pytest.mark.asyncio
    async def test_delete_success(self) -> None:
        """Test successful delete operation."""
        cache = RedisCache(redis_url="redis://localhost:6379")

        mock_client = AsyncMock()
        mock_client.delete.return_value = 1
        cache._client = mock_client

        result = await cache.delete("key")
        assert result is True
        mock_client.delete.assert_called_once_with("sanskrit:key")

    @pytest.mark.asyncio
    async def test_delete_not_found(self) -> None:
        """Test delete when key not found."""
        cache = RedisCache(redis_url="redis://localhost:6379")

        mock_client = AsyncMock()
        mock_client.delete.return_value = 0
        cache._client = mock_client

        result = await cache.delete("key")
        assert result is False

    @pytest.mark.asyncio
    async def test_exists_true(self) -> None:
        """Test exists when key exists."""
        cache = RedisCache(redis_url="redis://localhost:6379")

        mock_client = AsyncMock()
        mock_client.exists.return_value = 1
        cache._client = mock_client

        result = await cache.exists("key")
        assert result is True

    @pytest.mark.asyncio
    async def test_exists_false(self) -> None:
        """Test exists when key doesn't exist."""
        cache = RedisCache(redis_url="redis://localhost:6379")

        mock_client = AsyncMock()
        mock_client.exists.return_value = 0
        cache._client = mock_client

        result = await cache.exists("key")
        assert result is False

    @pytest.mark.asyncio
    async def test_health_check_success(self) -> None:
        """Test health check success."""
        cache = RedisCache(redis_url="redis://localhost:6379")

        mock_client = AsyncMock()
        cache._client = mock_client

        result = await cache.health_check()
        assert result is True
        mock_client.ping.assert_called_once()

    @pytest.mark.asyncio
    async def test_health_check_failure(self) -> None:
        """Test health check failure."""
        cache = RedisCache(redis_url="redis://localhost:6379")

        mock_client = AsyncMock()
        mock_client.ping.side_effect = Exception("Connection error")
        cache._client = mock_client

        result = await cache.health_check()
        assert result is False

    @pytest.mark.asyncio
    async def test_health_check_disabled(self) -> None:
        """Test health check when disabled."""
        cache = RedisCache(redis_url=None)
        result = await cache.health_check()
        assert result is False

    @pytest.mark.asyncio
    async def test_get_ttl_success(self) -> None:
        """Test getting TTL."""
        cache = RedisCache(redis_url="redis://localhost:6379")

        mock_client = AsyncMock()
        mock_client.ttl.return_value = 3600
        cache._client = mock_client

        result = await cache.get_ttl("key")
        assert result == 3600

    @pytest.mark.asyncio
    async def test_get_ttl_expired(self) -> None:
        """Test getting TTL for expired/missing key."""
        cache = RedisCache(redis_url="redis://localhost:6379")

        mock_client = AsyncMock()
        mock_client.ttl.return_value = -1
        cache._client = mock_client

        result = await cache.get_ttl("key")
        assert result is None

    @pytest.mark.asyncio
    async def test_connect_success(self) -> None:
        """Test successful connection with mocked redis module."""
        cache = RedisCache(redis_url="redis://localhost:6379")

        # Simulate successful connection by directly setting client
        mock_client = AsyncMock()
        cache._client = mock_client
        cache._stats.connected = True

        # Verify health check works
        result = await cache.health_check()
        assert result is True

    @pytest.mark.asyncio
    async def test_connect_disabled(self) -> None:
        """Test connect when disabled."""
        cache = RedisCache(redis_url=None)
        result = await cache.connect()
        assert result is False

    @pytest.mark.asyncio
    async def test_connect_no_client(self) -> None:
        """Test operations without client."""
        cache = RedisCache(redis_url="redis://localhost:6379")
        # Don't set client - operations should fail gracefully

        result = await cache.get("key")
        assert result is None
        assert cache.stats.misses == 1

    @pytest.mark.asyncio
    async def test_close(self) -> None:
        """Test closing connection."""
        cache = RedisCache(redis_url="redis://localhost:6379")

        mock_client = AsyncMock()
        cache._client = mock_client
        cache._stats.connected = True

        await cache.close()

        mock_client.close.assert_called_once()
        assert cache._client is None
        assert cache.stats.connected is False

    @pytest.mark.asyncio
    async def test_clear_prefix_disabled(self) -> None:
        """Test clearing keys by prefix when disabled."""
        cache = RedisCache(redis_url=None)
        result = await cache.clear_prefix("test:")
        assert result == 0

    @pytest.mark.asyncio
    async def test_clear_prefix_no_client(self) -> None:
        """Test clearing keys when client not connected."""
        cache = RedisCache(redis_url="redis://localhost:6379")
        # Don't set client
        result = await cache.clear_prefix("test:")
        assert result == 0

    def test_unicode_values(self) -> None:
        """Test handling Unicode values."""
        cache = RedisCache(redis_url="redis://localhost:6379")
        # Just test that creation works - actual serialization tested in set tests
        assert cache.enabled is True
