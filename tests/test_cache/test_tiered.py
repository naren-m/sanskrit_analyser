"""Tests for tiered cache coordinator."""

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from sanskrit_analyzer.cache import tiered as tiered_mod
from sanskrit_analyzer.cache.tiered import (
    TieredCache,
    TieredCacheConfig,
    TieredCacheStats,
    TierStats,
)
from tests._cases import check_cases

P = "PRODUCTION"
REDIS_URL = "redis://localhost:6379"
MEM_SQLITE = {"memory_enabled": True, "memory_max_size": 100, "redis_enabled": False,
              "sqlite_enabled": True}
ALL_TIERS = {**MEM_SQLITE, "redis_enabled": True, "redis_url": REDIS_URL}
MEM_REDIS = {**ALL_TIERS, "sqlite_enabled": False}
NONE = {"memory_enabled": False, "redis_enabled": False, "sqlite_enabled": False}


@pytest.fixture
def make_cache(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Factory: a TieredCache per row, each with its own SQLite file.

    HOME is redirected so the default-config row never writes the developer's
    real ~/.sanskrit_analyzer/corpus.db.
    """
    monkeypatch.setenv("HOME", str(tmp_path))
    n = iter(range(1000))

    def make(overrides: dict | None) -> TieredCache:
        if overrides is None:
            return TieredCache()
        return TieredCache(
            TieredCacheConfig(sqlite_path=str(tmp_path / f"t{next(n)}.db"), **overrides)
        )

    return make


def test_hit_rates() -> None:
    overall = TieredCacheStats(total_requests=100)
    overall.memory.hits, overall.redis.hits, overall.sqlite.hits = 60, 20, 10
    cases = [
        ("tier_no_accesses_is_zero", TierStats().hit_rate, 0.0),
        ("tier_hits_over_total", TierStats(hits=75, misses=25).hit_rate, 0.75),
        ("overall_no_requests_is_zero", TieredCacheStats().overall_hit_rate, 0.0),
        ("overall_sums_hits_across_tiers", overall.overall_hit_rate, 0.9),
    ]

    def check(got, expected):
        assert got == expected, got

    check_cases(cases, check)


def test_tier_status(make_cache) -> None:
    cases = [
        ("default_config_memory_and_sqlite", None,
         {"memory": True, "redis": False, "sqlite": True}),
        ("memory_only", {**NONE, "memory_enabled": True},
         {"memory": True, "redis": False, "sqlite": False}),
    ]

    def check(overrides, expected):
        assert make_cache(overrides).get_tier_status() == expected

    check_cases(cases, check)


def test_make_key(make_cache) -> None:
    cache = make_cache(MEM_SQLITE)
    key = cache.make_key("gacchati", P)
    assert key == cache.make_key("gacchati", P), "deterministic"
    assert key != cache.make_key("gacchati", "ACADEMIC"), "mode is part of the key"
    assert len(key) == 32

    # Bumping CACHE_SCHEMA_VERSION must invalidate every stored key.
    original = tiered_mod.CACHE_SCHEMA_VERSION
    try:
        tiered_mod.CACHE_SCHEMA_VERSION = original + 1
        assert cache.make_key("gacchati", P) != key
    finally:
        tiered_mod.CACHE_SCHEMA_VERSION = original


RESULT = {"segments": [{"surface": "test"}]}


async def _set(cache, result=RESULT) -> str:
    key = cache.make_key("test", P)
    await cache.set(key, "test", "test", P, result)
    return key


async def _set_then_get_hits_memory(cache):
    key = await _set(cache)
    assert await cache.get(key) == RESULT
    assert cache.stats.memory.hits == 1


async def _get_miss(cache):
    assert await cache.get("nonexistent") is None
    assert cache.stats.total_requests == 1
    assert cache.stats.memory.misses == 1


async def _stats_tracking(cache):
    key = await _set(cache, {"segments": []})
    await cache.get(key)
    await cache.get("nonexistent")
    stats = cache.stats
    assert (stats.total_requests, stats.memory.hits, stats.memory.misses) == (2, 1, 1)


async def _sqlite_hit_promotes_to_memory(cache):
    key = cache.make_key("test", P)
    cache._sqlite.set(key, "test", "test", P, RESULT)
    cache._memory.clear()
    assert await cache.get(key) == RESULT
    assert cache.stats.sqlite.hits == 1
    assert cache.stats.memory.promotions == 1
    # Second get is served by memory.
    assert await cache.get(key) == RESULT
    assert cache.stats.memory.hits == 1


async def _sqlite_read_error_is_a_miss(cache):
    # A corrupt SQLite row is treated as a miss, not a crash.
    key = cache.make_key("test", P)
    cache._sqlite.set(key, "test", "test", P, {"ok": 1})
    cache._memory.clear()
    with patch.object(cache._sqlite, "get", side_effect=ValueError("corrupt row")):
        assert await cache.get(key) is None
    assert cache.stats.sqlite.errors == 1


async def _memory_stores_a_copy(cache):
    # Mutating the result after set() must not corrupt the cached value.
    result = {"segments": [{"surface": "test"}]}
    key = await _set(cache, result)
    result["segments"][0]["surface"] = "MUTATED"
    assert await cache.get(key) == {"segments": [{"surface": "test"}]}


async def _exists_and_delete(cache):
    key = cache.make_key("test", P)
    assert not await cache.exists(key)
    await _set(cache, {})
    assert await cache.exists(key)
    assert await cache.delete(key) is True
    assert not await cache.exists(key)


async def _clear_memory_keeps_sqlite(cache):
    key = await _set(cache)
    await cache.clear_memory()
    assert cache._memory.get(key) is None
    assert cache._sqlite.get(key) is not None


async def _clear_all(cache):
    key = await _set(cache)
    await cache.clear_all()
    assert not await cache.exists(key)


async def _health_check(cache):
    assert await cache.health_check() == {"memory": True, "redis": False, "sqlite": True}


async def _no_tiers_is_always_a_miss(cache):
    assert await cache.get("key") is None
    await cache.set("key", "test", "test", P, {})  # must not raise
    assert await cache.get("key") is None


async def _redis_written_and_deleted(cache):
    client = AsyncMock()
    client.get.return_value = None
    client.delete.return_value = 1
    cache._redis._client = client
    key = await _set(cache, {"segments": []})
    client.setex.assert_called()
    await cache.delete(key)
    client.delete.assert_called()


async def _redis_hit_promotes_to_memory(cache):
    async def redis_get(key: str) -> dict:
        return RESULT

    cache._redis.get = redis_get
    cache._memory.clear()
    assert await cache.get(cache.make_key("test", P)) == RESULT
    assert cache.stats.redis.hits == 1
    assert cache.stats.memory.promotions == 1


async def _initialize_and_close_without_redis(cache):
    # No Redis is listening; initialize() must degrade, not raise.
    await cache.initialize()
    await cache.close()


# (id, TieredCacheConfig overrides, async scenario on a fresh cache)
SCENARIO_CASES = [
    ("set_then_get_hits_memory", MEM_SQLITE, _set_then_get_hits_memory),
    ("get_miss_counts_request_and_miss", MEM_SQLITE, _get_miss),
    ("stats_tracking", MEM_SQLITE, _stats_tracking),
    ("sqlite_hit_promotes_to_memory", MEM_SQLITE, _sqlite_hit_promotes_to_memory),
    ("sqlite_read_error_is_a_miss", MEM_SQLITE, _sqlite_read_error_is_a_miss),
    ("memory_stores_a_copy", MEM_SQLITE, _memory_stores_a_copy),
    ("exists_and_delete_span_tiers", MEM_SQLITE, _exists_and_delete),
    ("clear_memory_keeps_sqlite", MEM_SQLITE, _clear_memory_keeps_sqlite),
    ("clear_all", MEM_SQLITE, _clear_all),
    ("health_check_reports_each_tier", MEM_SQLITE, _health_check),
    ("no_tiers_is_always_a_miss", NONE, _no_tiers_is_always_a_miss),
    ("redis_written_and_deleted", ALL_TIERS, _redis_written_and_deleted),
    ("redis_hit_promotes_to_memory", MEM_REDIS, _redis_hit_promotes_to_memory),
    ("initialize_and_close_without_redis", ALL_TIERS, _initialize_and_close_without_redis),
]


def test_scenarios(make_cache) -> None:
    check_cases(
        SCENARIO_CASES,
        lambda overrides, scenario: asyncio.run(scenario(make_cache(overrides))),
    )
