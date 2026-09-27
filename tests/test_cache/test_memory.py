"""Tests for memory LRU cache."""

import threading

import pytest

from sanskrit_analyzer.cache.memory import CacheStats, LRUCache
from tests._cases import check_cases


def test_stats_hit_rate_and_reset() -> None:
    cases = [
        ("no_accesses_is_zero_not_div_by_zero", CacheStats(), 0.0),
        ("hits_over_total", CacheStats(hits=75, misses=25), 0.75),
    ]

    def check(stats: CacheStats, rate: float) -> None:
        assert stats.hit_rate == rate, stats.hit_rate

    check_cases(cases, check)

    # reset() zeroes the counters but leaves size alone: size is live state
    # refreshed from the cache, not a counter.
    stats = CacheStats(hits=100, misses=50, evictions=10, size=5)
    stats.reset()
    assert (stats.hits, stats.misses, stats.evictions, stats.size) == (0, 0, 0, 5)


def test_make_key() -> None:
    cache = LRUCache(max_size=5)
    key = cache.make_key("gacchati", "PRODUCTION")
    assert key == cache.make_key("gacchati", "PRODUCTION"), "deterministic"
    assert key != cache.make_key("gacchati", "EDUCATIONAL"), "mode is part of the key"
    assert key != cache.make_key("pazyati", "PRODUCTION"), "text is part of the key"
    assert len(key) == 32, "truncated sha256"


COMPLEX = {
    "segments": [{"surface": "gacchati", "lemma": "gam"}],
    "confidence": 0.95,
    "nested": {"list": [1, 2, 3]},
}

# (id, max_size, ops, expected). Each op is (method, *args); ``returns`` lists
# every op's return value in order. ``keys`` is the LRU order, oldest first.
# ``access`` reads the entry's access_count.
OP_CASES = [
    ("empty_cache", 5, [], {"returns": [], "keys": []}),
    ("set_then_get", 5, [("set", "key1", "value1"), ("get", "key1")],
     {"returns": [None, "value1"]}),
    ("get_missing_is_none_and_a_miss", 5, [("get", "nonexistent")],
     {"returns": [None], "stats": {"misses": 1}}),
    ("complex_values_round_trip", 5, [("set", "key", COMPLEX), ("get", "key")],
     {"returns": [None, COMPLEX]}),
    ("get_moves_key_to_most_recent", 5,
     [("set", "a", 1), ("set", "b", 2), ("set", "c", 3), ("get", "a")],
     {"keys": ["b", "c", "a"]}),
    ("get_then_set_keeps_lru_order", 5,
     [("set", "a", 1), ("set", "b", 2), ("set", "c", 3), ("get", "a"), ("set", "d", 4)],
     {"keys": ["b", "c", "a", "d"]}),
    ("full_cache_evicts_oldest", 3,
     [("set", "a", 1), ("set", "b", 2), ("set", "c", 3), ("set", "d", 4),
      ("get", "a"), ("get", "b"), ("get", "c"), ("get", "d")],
     {"returns": [None] * 4 + [None, 2, 3, 4], "size": 3}),
    ("evictions_are_counted", 2,
     [("set", "a", 1), ("set", "b", 2), ("set", "c", 3), ("set", "d", 4)],
     {"stats": {"evictions": 2}}),
    ("set_existing_overwrites_in_place", 5,
     [("set", "key", "value1"), ("set", "key", "value2"), ("get", "key")],
     {"returns": [None, None, "value2"], "size": 1}),
    ("delete_existing_true", 5, [("set", "key", "value"), ("delete", "key"), ("get", "key")],
     {"returns": [None, True, None], "size": 0}),
    ("delete_missing_false", 5, [("delete", "nonexistent")], {"returns": [False]}),
    # clear empties the cache and resets the counters; the get after it is
    # the only miss left.
    ("clear_empties_and_resets_stats", 5,
     [("set", "a", 1), ("set", "b", 2), ("get", "a"), ("get", "x"), ("clear",), ("get", "a")],
     {"returns": [None, None, 1, None, None, None], "size": 0,
      "stats": {"hits": 0, "misses": 1}}),
    ("contains", 5, [("set", "key", "value"), ("contains", "key"), ("contains", "other")],
     {"returns": [None, True, False]}),
    ("contains_does_not_touch_lru", 5, [("set", "a", 1), ("set", "b", 2), ("contains", "a")],
     {"keys": ["a", "b"]}),
    ("hits_and_misses_counted", 5,
     [("set", "key", "value"), ("get", "key"), ("get", "key"), ("get", "missing")],
     {"stats": {"hits": 2, "misses": 1, "hit_rate": pytest.approx(2 / 3)}}),
    ("get_many_skips_missing", 5,
     [("set", "a", 1), ("set", "b", 2), ("set", "c", 3), ("get_many", ["a", "b", "missing"])],
     {"returns": [None, None, None, {"a": 1, "b": 2}]}),
    ("set_many", 5,
     [("set_many", {"a": 1, "b": 2, "c": 3}), ("get", "a"), ("get", "b"), ("get", "c")],
     {"returns": [None, 1, 2, 3]}),
    ("get_counts_accesses", 5,
     [("set", "key", "value"), ("get", "key"), ("get", "key"), ("get", "key")],
     {"access": {"key": 3}}),
]


def test_operations() -> None:
    def check(max_size, ops, expected):
        cache = LRUCache(max_size=max_size)
        assert cache.max_size == max_size
        returns = [getattr(cache, name)(*args) for name, *args in ops]
        if "returns" in expected:
            assert returns == expected["returns"], returns
        if "keys" in expected:
            assert cache.keys() == expected["keys"], cache.keys()
        if "size" in expected:
            assert cache.size == expected["size"], cache.size
        for name, value in expected.get("stats", {}).items():
            assert getattr(cache.stats, name) == value, name
        for key, count in expected.get("access", {}).items():
            assert cache._cache[key].access_count == count

    check_cases(OP_CASES, check)


def test_thread_safety() -> None:
    """Concurrent set/get from 10 threads never returns another key's value."""
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
