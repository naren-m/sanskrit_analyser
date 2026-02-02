"""Tiered caching for analysis results."""

from sanskrit_analyzer.cache.memory import CacheEntry, CacheStats, LRUCache
from sanskrit_analyzer.cache.sqlite_corpus import CorpusEntry, CorpusStats, SQLiteCorpus

__all__ = [
    "CacheEntry",
    "CacheStats",
    "CorpusEntry",
    "CorpusStats",
    "LRUCache",
    "SQLiteCorpus",
]
