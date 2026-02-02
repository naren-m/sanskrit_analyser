"""Tiered caching for analysis results."""

from sanskrit_analyzer.cache.memory import CacheEntry, CacheStats, LRUCache
from sanskrit_analyzer.cache.redis_cache import RedisCache, RedisCacheStats
from sanskrit_analyzer.cache.sqlite_corpus import CorpusEntry, CorpusStats, SQLiteCorpus
from sanskrit_analyzer.cache.tiered import TieredCache, TieredCacheConfig, TieredCacheStats

__all__ = [
    "CacheEntry",
    "CacheStats",
    "CorpusEntry",
    "CorpusStats",
    "LRUCache",
    "RedisCache",
    "RedisCacheStats",
    "SQLiteCorpus",
    "TieredCache",
    "TieredCacheConfig",
    "TieredCacheStats",
]
