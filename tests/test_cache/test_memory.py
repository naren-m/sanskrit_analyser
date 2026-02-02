"""Tests for memory LRU cache."""

import threading
from concurrent.futures import ThreadPoolExecutor

import pytest

from sanskrit_analyzer.cache.memory import CacheEntry, CacheStats, LRUCache


class TestCacheStats:
    """Tests for CacheStats dataclass."""

    def test_default_values(self) -> None:
        """Test default statistics values."""
        stats = CacheStats()
        assert stats.hits == 0
        assert stats.misses == 0
        assert stats.evictions == 0
        assert stats.size == 0

    def test_hit_rate_empty(self) -> None:
        """Test hit rate with no accesses."""
        stats = CacheStats()
        assert stats.hit_rate == 0.0

    def test_hit_rate_calculation(self) -> None:
        """Test hit rate calculation."""
        stats = CacheStats(hits=75, misses=25)
        assert stats.hit_rate == 0.75

    def test_reset(self) -> None:
        """Test statistics reset."""
        stats = CacheStats(hits=100, misses=50, evictions=10, size=5)
        stats.reset()
        assert stats.hits == 0
        assert stats.misses == 0
        assert stats.evictions == 0
        # Size is not reset by reset()
        assert stats.size == 5


class TestCacheEntry:
    """Tests for CacheEntry dataclass."""

    def test_create_entry(self) -> None:
        """Test creating a cache entry."""
        entry = CacheEntry(value={"test": "data"})
        assert entry.value == {"test": "data"}
        assert entry.access_count == 0


class TestLRUCache:
    """Tests for LRUCache class."""

    @pytest.fixture
    def cache(self) -> LRUCache:
        """Create a cache instance."""
        return LRUCache(max_size=5)

    def test_init(self, cache: LRUCache) -> None:
        """Test cache initialization."""
        assert cache.size == 0
        assert cache.max_size == 5

    def test_make_key(self, cache: LRUCache) -> None:
        """Test cache key generation."""
        key1 = cache.make_key("gacchati", "PRODUCTION")
        key2 = cache.make_key("gacchati", "PRODUCTION")
        key3 = cache.make_key("gacchati", "EDUCATIONAL")
        key4 = cache.make_key("pazyati", "PRODUCTION")

        # Same inputs should produce same key
        assert key1 == key2
        # Different mode should produce different key
        assert key1 != key3
        # Different text should produce different key
        assert key1 != key4
        # Key should be 32 chars (truncated hash)
        assert len(key1) == 32

    def test_set_and_get(self, cache: LRUCache) -> None:
        """Test basic set and get operations."""
        cache.set("key1", "value1")
        assert cache.get("key1") == "value1"

    def test_get_missing(self, cache: LRUCache) -> None:
        """Test getting a missing key."""
        assert cache.get("nonexistent") is None

    def test_get_updates_lru_order(self, cache: LRUCache) -> None:
        """Test that get updates LRU order."""
        cache.set("a", 1)
        cache.set("b", 2)
        cache.set("c", 3)

        # Access 'a' to make it most recently used
        cache.get("a")

        # Keys should be in LRU order: b, c, a
        keys = cache.keys()
        assert keys == ["b", "c", "a"]

    def test_eviction(self) -> None:
        """Test LRU eviction when cache is full."""
        cache = LRUCache(max_size=3)
        cache.set("a", 1)
        cache.set("b", 2)
        cache.set("c", 3)
        cache.set("d", 4)  # Should evict 'a'

        assert cache.get("a") is None
        assert cache.get("b") == 2
        assert cache.get("c") == 3
        assert cache.get("d") == 4
        assert cache.size == 3

    def test_eviction_stats(self) -> None:
        """Test eviction counter in stats."""
        cache = LRUCache(max_size=2)
        cache.set("a", 1)
        cache.set("b", 2)
        cache.set("c", 3)  # Evicts 'a'
        cache.set("d", 4)  # Evicts 'b'

        assert cache.stats.evictions == 2

    def test_update_existing(self, cache: LRUCache) -> None:
        """Test updating an existing key."""
        cache.set("key", "value1")
        cache.set("key", "value2")

        assert cache.get("key") == "value2"
        assert cache.size == 1

    def test_delete(self, cache: LRUCache) -> None:
        """Test deleting an entry."""
        cache.set("key", "value")
        assert cache.delete("key") is True
        assert cache.get("key") is None
        assert cache.size == 0

    def test_delete_missing(self, cache: LRUCache) -> None:
        """Test deleting a missing key."""
        assert cache.delete("nonexistent") is False

    def test_clear(self, cache: LRUCache) -> None:
        """Test clearing the cache."""
        cache.set("a", 1)
        cache.set("b", 2)
        cache.clear()

        assert cache.size == 0
        # Stats are reset by clear
        assert cache.stats.hits == 0
        assert cache.stats.misses == 0
        # After clear, getting a key will be a miss
        assert cache.get("a") is None
        assert cache.stats.misses == 1  # Now we have a miss

    def test_contains(self, cache: LRUCache) -> None:
        """Test contains check."""
        cache.set("key", "value")
        assert cache.contains("key") is True
        assert cache.contains("other") is False

    def test_contains_does_not_update_lru(self, cache: LRUCache) -> None:
        """Test that contains doesn't update LRU order."""
        cache.set("a", 1)
        cache.set("b", 2)

        cache.contains("a")  # Should not move 'a'

        # Order should still be: a, b
        keys = cache.keys()
        assert keys == ["a", "b"]

    def test_hit_miss_stats(self, cache: LRUCache) -> None:
        """Test hit and miss statistics."""
        cache.set("key", "value")
        cache.get("key")  # Hit
        cache.get("key")  # Hit
        cache.get("missing")  # Miss

        stats = cache.stats
        assert stats.hits == 2
        assert stats.misses == 1
        assert stats.hit_rate == pytest.approx(2 / 3)

    def test_get_many(self, cache: LRUCache) -> None:
        """Test getting multiple keys."""
        cache.set("a", 1)
        cache.set("b", 2)
        cache.set("c", 3)

        results = cache.get_many(["a", "b", "missing"])
        assert results == {"a": 1, "b": 2}

    def test_set_many(self, cache: LRUCache) -> None:
        """Test setting multiple keys."""
        cache.set_many({"a": 1, "b": 2, "c": 3})

        assert cache.get("a") == 1
        assert cache.get("b") == 2
        assert cache.get("c") == 3

    def test_access_count(self, cache: LRUCache) -> None:
        """Test access count tracking."""
        cache.set("key", "value")
        cache.get("key")
        cache.get("key")
        cache.get("key")

        # Access internal state (for testing only)
        entry = cache._cache["key"]
        assert entry.access_count == 3

    def test_thread_safety(self) -> None:
        """Test concurrent access from multiple threads."""
        cache = LRUCache(max_size=100)
        errors: list[Exception] = []

        def worker(thread_id: int) -> None:
            try:
                for i in range(100):
                    key = f"thread_{thread_id}_key_{i}"
                    cache.set(key, i)
                    value = cache.get(key)
                    # Value might be evicted, so it could be None
                    if value is not None and value != i:
                        errors.append(ValueError(f"Unexpected value: {value}"))
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0, f"Thread errors: {errors}"

    def test_complex_values(self, cache: LRUCache) -> None:
        """Test storing complex values."""
        complex_value = {
            "segments": [{"surface": "gacchati", "lemma": "gam"}],
            "confidence": 0.95,
            "nested": {"list": [1, 2, 3]},
        }
        cache.set("key", complex_value)
        result = cache.get("key")
        assert result == complex_value

    def test_keys_order(self) -> None:
        """Test that keys() returns LRU order."""
        cache = LRUCache(max_size=5)
        cache.set("a", 1)
        cache.set("b", 2)
        cache.set("c", 3)

        # Access 'a' to make it most recently used
        cache.get("a")
        # Add new key
        cache.set("d", 4)

        # Order should be: b, c, a, d (oldest to newest)
        assert cache.keys() == ["b", "c", "a", "d"]
