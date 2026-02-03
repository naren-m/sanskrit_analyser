"""In-memory LRU cache for Sanskrit analysis results."""

import hashlib
import threading
from collections import OrderedDict
from dataclasses import dataclass
from typing import Any


@dataclass
class CacheStats:
    """Statistics for cache performance monitoring."""

    hits: int = 0
    misses: int = 0
    evictions: int = 0
    size: int = 0

    @property
    def hit_rate(self) -> float:
        """Calculate cache hit rate."""
        total = self.hits + self.misses
        if total == 0:
            return 0.0
        return self.hits / total

    def reset(self) -> None:
        """Reset all statistics."""
        self.hits = 0
        self.misses = 0
        self.evictions = 0


@dataclass
class CacheEntry:
    """A single cache entry with metadata."""

    value: Any
    access_count: int = 0


class LRUCache:
    """Thread-safe LRU (Least Recently Used) cache for analysis results.

    This cache stores analysis results keyed by normalized text + mode,
    evicting the least recently used entries when capacity is reached.

    Example:
        cache = LRUCache(max_size=1000)
        key = cache.make_key("gacchati", "PRODUCTION")
        cache.set(key, analysis_result)
        result = cache.get(key)
    """

    def __init__(self, max_size: int = 1000) -> None:
        """Initialize the LRU cache.

        Args:
            max_size: Maximum number of entries to store.
        """
        self._max_size = max_size
        self._cache: OrderedDict[str, CacheEntry] = OrderedDict()
        self._lock = threading.RLock()
        self._stats = CacheStats()

    @property
    def stats(self) -> CacheStats:
        """Get cache statistics."""
        with self._lock:
            self._stats.size = len(self._cache)
            return self._stats

    @property
    def size(self) -> int:
        """Get current cache size."""
        with self._lock:
            return len(self._cache)

    @property
    def max_size(self) -> int:
        """Get maximum cache size."""
        return self._max_size

    def make_key(self, text: str, mode: str = "PRODUCTION") -> str:
        """Generate a cache key from text and mode.

        Args:
            text: Normalized SLP1 text.
            mode: Analysis mode (PRODUCTION, EDUCATIONAL, ACADEMIC).

        Returns:
            A unique cache key string.
        """
        # Use hash for consistent key length and fast comparison
        content = f"{mode}:{text}"
        return hashlib.sha256(content.encode("utf-8")).hexdigest()[:32]

    def get(self, key: str) -> Any | None:
        """Get a value from the cache.

        If found, the entry is moved to the end (most recently used).

        Args:
            key: Cache key.

        Returns:
            Cached value or None if not found.
        """
        with self._lock:
            if key not in self._cache:
                self._stats.misses += 1
                return None

            # Move to end (most recently used)
            self._cache.move_to_end(key)
            entry = self._cache[key]
            entry.access_count += 1
            self._stats.hits += 1
            return entry.value

    def set(self, key: str, value: Any) -> None:
        """Store a value in the cache.

        If the cache is at capacity, the least recently used entry is evicted.

        Args:
            key: Cache key.
            value: Value to store.
        """
        with self._lock:
            if key in self._cache:
                # Update existing entry and move to end
                self._cache[key].value = value
                self._cache.move_to_end(key)
                return

            # Evict if at capacity
            while len(self._cache) >= self._max_size:
                self._cache.popitem(last=False)
                self._stats.evictions += 1

            # Add new entry
            self._cache[key] = CacheEntry(value=value)

    def delete(self, key: str) -> bool:
        """Delete an entry from the cache.

        Args:
            key: Cache key.

        Returns:
            True if entry was deleted, False if not found.
        """
        with self._lock:
            if key in self._cache:
                del self._cache[key]
                return True
            return False

    def clear(self) -> None:
        """Clear all entries from the cache."""
        with self._lock:
            self._cache.clear()
            self._stats.reset()

    def contains(self, key: str) -> bool:
        """Check if a key exists in the cache.

        Note: This does NOT update the LRU order.

        Args:
            key: Cache key.

        Returns:
            True if key exists.
        """
        with self._lock:
            return key in self._cache

    def keys(self) -> list[str]:
        """Get all cache keys (in LRU order, oldest first).

        Returns:
            List of cache keys.
        """
        with self._lock:
            return list(self._cache.keys())

    def get_many(self, keys: list[str]) -> dict[str, Any]:
        """Get multiple values from the cache.

        Args:
            keys: List of cache keys.

        Returns:
            Dictionary of found key-value pairs.
        """
        results: dict[str, Any] = {}
        for key in keys:
            value = self.get(key)
            if value is not None:
                results[key] = value
        return results

    def set_many(self, items: dict[str, Any]) -> None:
        """Store multiple values in the cache.

        Args:
            items: Dictionary of key-value pairs.
        """
        for key, value in items.items():
            self.set(key, value)
