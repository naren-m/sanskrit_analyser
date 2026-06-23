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


requires_dharmamitra = pytest.mark.skipif(
    not os.environ.get("DEEPREAD_DHARMAMITRA_TESTS"),
    reason="set DEEPREAD_DHARMAMITRA_TESTS=1 to run the live dharmamitra API test",
)


@requires_dharmamitra
def test_segment_splits_compound_live():
    words = dseg.segment("इक्ष्वाकुवंशप्रभवो रामो नाम")
    assert words and any("ikṣvāku" in w for w in words)
