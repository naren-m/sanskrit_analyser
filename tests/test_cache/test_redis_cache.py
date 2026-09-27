"""Tests for Redis cache.

The Redis client is the network boundary, so it is an ``AsyncMock``; every
row builds a fresh cache, runs one call, and checks the result, the stats it
leaves behind, and (where the key prefix or TTL matters) what reached Redis.
"""

import asyncio
from unittest.mock import AsyncMock

from sanskrit_analyzer.cache.redis_cache import RedisCache, RedisCacheStats
from tests._cases import check_cases

URL = "redis://localhost:6379"
ON = {"redis_url": URL}
OFF = {"redis_url": None}
VALUE = {"test": "value"}
DOWN = Exception("Connection error")


def _client(spec: dict | None) -> AsyncMock | None:
    """Build a fake client: each key is a method, an Exception value raises."""
    if spec is None:
        return None
    client = AsyncMock()
    for method, result in spec.items():
        if isinstance(result, Exception):
            getattr(client, method).side_effect = result
        else:
            getattr(client, method).return_value = result
    return client


def test_hit_rate() -> None:
    cases = [
        ("no_accesses_is_zero_not_div_by_zero", 0, 0, 0.0),
        ("hits_over_total", 75, 25, 0.75),
    ]

    def check(hits, misses, expected):
        assert RedisCacheStats(hits=hits, misses=misses).hit_rate == expected

    check_cases(cases, check)


def _setex_used_prefix_and_default_ttl(cache, client):
    key, ttl, payload = client.setex.call_args[0]
    assert (key, ttl) == ("sanskrit:key", 3600)
    assert '"test": "value"' in payload


def _setex_used_custom_ttl(cache, client):
    assert client.setex.call_args[0][1] == 60


def _get_used_prefix(cache, client):
    client.get.assert_called_once_with("sanskrit:key")


def _delete_used_prefix(cache, client):
    client.delete.assert_called_once_with("sanskrit:key")


def _pinged(cache, client):
    client.ping.assert_called_once()


async def _close_connected(cache):
    cache._stats.connected = True
    await cache.close()


def _close_dropped_client(cache, client):
    client.close.assert_called_once()
    assert cache._client is None
    assert cache.stats.connected is False


# (id, RedisCache kwargs, fake client spec or None for "never connected",
#  call, expected result, expected stats, extra check on (cache, client))
OP_CASES = [
    # disabled (no URL): every op is a harmless no-op, get still counts a miss
    ("disabled_get_is_miss", OFF, None, lambda c: c.get("key"), None, {"misses": 1}, None),
    ("disabled_set_refused", OFF, None, lambda c: c.set("key", VALUE), False, {}, None),
    ("disabled_health_false", OFF, None, lambda c: c.health_check(), False, {}, None),
    ("disabled_connect_false", OFF, None, lambda c: c.connect(), False, {}, None),
    ("disabled_clear_prefix_zero", OFF, None, lambda c: c.clear_prefix("test:"), 0, {}, None),
    # enabled but never connected: degrade gracefully instead of raising
    ("unconnected_get_is_miss", ON, None, lambda c: c.get("key"), None, {"misses": 1}, None),
    ("unconnected_clear_prefix_zero", ON, None, lambda c: c.clear_prefix("test:"), 0, {}, None),
    # get
    ("get_hit_decodes_json_under_prefix", ON, {"get": '{"test": "value"}'},
     lambda c: c.get("key"), VALUE, {"hits": 1}, _get_used_prefix),
    ("get_none_is_miss", ON, {"get": None}, lambda c: c.get("key"), None, {"misses": 1}, None),
    ("get_error_counts_error_and_miss", ON, {"get": DOWN},
     lambda c: c.get("key"), None, {"errors": 1, "misses": 1}, None),
    # set
    ("set_uses_prefix_and_default_ttl", {**ON, "default_ttl": 3600}, {},
     lambda c: c.set("key", VALUE), True, {}, _setex_used_prefix_and_default_ttl),
    ("set_custom_ttl_overrides_default", ON, {},
     lambda c: c.set("key", VALUE, ttl=60), True, {}, _setex_used_custom_ttl),
    ("set_error_returns_false", ON, {"setex": DOWN},
     lambda c: c.set("key", VALUE), False, {"errors": 1}, None),
    # delete / exists coerce Redis integer replies to bool
    ("delete_found_true_under_prefix", ON, {"delete": 1},
     lambda c: c.delete("key"), True, {}, _delete_used_prefix),
    ("delete_not_found_false", ON, {"delete": 0}, lambda c: c.delete("key"), False, {}, None),
    ("exists_one_true", ON, {"exists": 1}, lambda c: c.exists("key"), True, {}, None),
    ("exists_zero_false", ON, {"exists": 0}, lambda c: c.exists("key"), False, {}, None),
    # health / ttl / close
    ("health_pings", ON, {}, lambda c: c.health_check(), True, {}, _pinged),
    ("health_ping_error_false", ON, {"ping": DOWN}, lambda c: c.health_check(), False, {}, None),
    ("ttl_positive_returned", ON, {"ttl": 3600}, lambda c: c.get_ttl("key"), 3600, {}, None),
    ("ttl_expired_or_missing_is_none", ON, {"ttl": -1}, lambda c: c.get_ttl("key"), None, {}, None),
    ("close_drops_client_and_connected", ON, {}, _close_connected, None, {}, _close_dropped_client),
]


def test_operations() -> None:
    def check(kwargs, spec, call, expected, stats, verify):
        cache = RedisCache(**kwargs)
        assert cache.enabled is (kwargs["redis_url"] is not None)
        client = _client(spec)
        cache._client = client
        assert asyncio.run(call(cache)) == expected
        for name, count in stats.items():
            assert getattr(cache.stats, name) == count, name
        if verify:
            verify(cache, client)

    check_cases(OP_CASES, check)


def test_make_key_uses_configured_prefix() -> None:
    cache = RedisCache(redis_url=URL, key_prefix="test:")
    assert cache._make_key("mykey") == "test:mykey"
