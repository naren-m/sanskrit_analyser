"""Tests for the Dharmamitra ByT5 segmenter helpers.

Pure parsing/cleaning/transliteration logic is tested offline. The live
``segment`` call hits an external API and is gated behind
``DEEPREAD_DHARMAMITRA_TESTS=1`` (kept off so the suite stays deterministic).
"""

import os

import pytest

from sanskrit_analyzer.deep_read import dharmamitra_segmenter as dseg


def test_parse_results_strips_leading_marker():
    # The API prefixes a per-sentence marker token (e.g. "9 " or "R ").
    assert dseg._parse_results("9 ikṣvāku_vaṃśa_prabhava_") == [
        "ikṣvāku", "vaṃśa", "prabhava",
    ]
    assert dseg._parse_results("R rāma_nāma_") == ["rāma", "nāma"]


def test_parse_results_no_marker():
    assert dseg._parse_results("rāma_nāma") == ["rāma", "nāma"]


def test_parse_results_empty():
    assert dseg._parse_results("") == []
    assert dseg._parse_results(None) == []


def test_clean_strips_dandas_digits_and_punctuation():
    # "।।1.1.8।।" and surrounding punctuation must not leak into the IAST.
    cleaned = dseg._clean("रामो नाम ।।1.1.8।।")
    assert "।" not in cleaned and "1" not in cleaned
    assert cleaned == "रामो नाम"


def test_dev_to_iast_and_back():
    iast = dseg.dev_to_iast("राम")
    assert iast == "rāma"
    assert dseg.iast_to_devanagari("rāma") == "राम"


def test_segment_empty_returns_empty_list_without_network():
    # Empty/whitespace input is handled locally; no request is made.
    assert dseg.segment("") == []
    assert dseg.segment("   ॥  ") == []


def test_env_timeout_defaults_on_bad_value(monkeypatch):
    # A malformed env value must not raise at import/parse time.
    monkeypatch.setenv("DHARMAMITRA_TIMEOUT", "not-a-number")
    assert dseg._env_timeout() == 30.0


def test_env_timeout_parses_valid_value(monkeypatch):
    monkeypatch.setenv("DHARMAMITRA_TIMEOUT", "12.5")
    assert dseg._env_timeout() == 12.5


def test_post_with_retries_retries_transient(monkeypatch):
    # A transient ConnectionError is retried, then None is returned.
    import requests

    calls = {"n": 0}

    def flaky_post(*args, **kwargs):
        calls["n"] += 1
        raise requests.exceptions.ConnectionError("refused")

    monkeypatch.setattr(dseg.requests, "post", flaky_post)
    monkeypatch.setattr(dseg.time, "sleep", lambda *_: None)

    assert dseg._post_with_retries("rama") is None
    assert calls["n"] == dseg._MAX_RETRIES + 1


def test_post_with_retries_no_retry_on_4xx(monkeypatch):
    # A non-transient HTTP 4xx fails fast (single attempt).
    import requests

    calls = {"n": 0}

    def bad_request(*args, **kwargs):
        calls["n"] += 1
        resp = requests.Response()
        resp.status_code = 400
        raise requests.exceptions.HTTPError(response=resp)

    monkeypatch.setattr(dseg.requests, "post", bad_request)
    monkeypatch.setattr(dseg.time, "sleep", lambda *_: None)

    assert dseg._post_with_retries("rama") is None
    assert calls["n"] == 1


def test_post_with_retries_succeeds_after_transient(monkeypatch):
    # Recovers on a later attempt and returns the results payload.
    import requests

    calls = {"n": 0}

    class _Resp:
        def raise_for_status(self):
            pass

        def json(self):
            return {"results": ["9 rama_nama_"]}

    def eventually_ok(*args, **kwargs):
        calls["n"] += 1
        if calls["n"] == 1:
            raise requests.exceptions.Timeout("slow")
        return _Resp()

    monkeypatch.setattr(dseg.requests, "post", eventually_ok)
    monkeypatch.setattr(dseg.time, "sleep", lambda *_: None)

    assert dseg._post_with_retries("rama") == ["9 rama_nama_"]
    assert calls["n"] == 2


requires_dharmamitra = pytest.mark.skipif(
    not os.environ.get("DEEPREAD_DHARMAMITRA_TESTS"),
    reason="set DEEPREAD_DHARMAMITRA_TESTS=1 to run the live dharmamitra API test",
)


@requires_dharmamitra
def test_segment_splits_compound_live():
    words = dseg.segment("इक्ष्वाकुवंशप्रभवो रामो नाम")
    assert words and any("ikṣvāku" in w for w in words)
