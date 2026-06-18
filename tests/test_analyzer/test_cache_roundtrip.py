"""Pin the cache (de)serialization path for verbs that carry a dhatu.

Regression coverage for the ``_result_to_tree`` dhatu reconstruction, which
previously crashed with ``TypeError: DhatuInfo.__init__() got an unexpected
keyword argument 'meaning'``. That path only fires on a cache HIT for a word
that actually has a dhatu — something that never happened while the
segmentation/transliteration bug suppressed verb dhatus, so it was never
exercised by the golden/segmentation suites (which disable caching).

Two angles are covered:
  1. A full analyze -> cache -> analyze round-trip (caching ENABLED on a
     throwaway sqlite path) for a COMMON_DHATUS root (``gam``).
  2. A direct ``_result_to_tree`` rebuild for a NON-common root (``paT``),
     which can't be produced reliably by the live engine but must still
     survive the round-trip via the minimal-DhatuInfo fallback.
"""

import asyncio

import pytest

from sanskrit_analyzer import Analyzer, AnalysisMode
from sanskrit_analyzer.config import Config


def _make_analyzer_with_cache(tmp_path):
    """Analyzer with the in-memory + a throwaway sqlite cache (no redis)."""
    config = Config()
    config.cache.redis_enabled = False
    config.cache.sqlite_enabled = True
    config.cache.sqlite_path = str(tmp_path / "roundtrip_corpus.db")
    return Analyzer(config)


def _words(tree):
    return [
        w
        for p in tree.parse_forest[:1]
        for sg in p.sandhi_groups
        for w in sg.base_words
    ]


def test_common_dhatu_survives_cache_roundtrip(tmp_path):
    """A COMMON_DHATUS verb keeps its dhatu through analyze -> cache -> analyze."""
    az = _make_analyzer_with_cache(tmp_path)

    async def go():
        # First call populates the cache (and produces the dhatu live).
        first = await az.analyze("स गच्छति वनम्", mode=AnalysisMode.EDUCATIONAL)
        # Second call is a cache HIT -> goes through _result_to_tree, which is
        # the path that used to raise TypeError.
        second = await az.analyze("स गच्छति वनम्", mode=AnalysisMode.EDUCATIONAL)
        return first, second

    first, second = asyncio.run(go())

    first_roots = {w.dhatu.dhatu for w in _words(first) if w.dhatu}
    second_roots = {w.dhatu.dhatu for w in _words(second) if w.dhatu}

    assert "gam" in first_roots, "live analysis should attach √gam"
    assert "gam" in second_roots, "dhatu must survive the cache round-trip"


def test_noncommon_dhatu_rebuilds_from_cached_dict():
    """A non-COMMON_DHATUS root rebuilds via the minimal-DhatuInfo fallback."""
    az = Analyzer(Config())

    cached = {
        "original_text": "paWati",
        "normalized_slp1": "paWati",
        "mode": "educational",
        "confidence": {"overall": 1.0},
        "parse_forest": [
            {
                "sandhi_groups": [
                    {
                        "surface_form": "paWati",
                        "base_words": [
                            {
                                "lemma": "paT",
                                "surface_form": "paWati",
                                "morphology": {"pos": "verb"},
                                "dhatu": {
                                    "dhatu": "paT",  # NOT in COMMON_DHATUS
                                    "meaning": "to read",
                                    "gana": 1,
                                    "pada": "parasmaipada",
                                    "meanings": ["to read"],
                                },
                                "confidence": 1.0,
                            }
                        ],
                    }
                ]
            }
        ],
    }

    tree = az._result_to_tree(cached)
    words = _words(tree)

    assert len(words) == 1
    dhatu = words[0].dhatu
    assert dhatu is not None, "non-common dhatu must rebuild, not be dropped"
    assert dhatu.dhatu == "paT"
    # The fallback maps the serialized singular 'meaning' into 'meanings'.
    assert "to read" in dhatu.meanings
    # Required scripts field must be populated (its absence was the crash).
    assert dhatu.scripts is not None
    assert dhatu.scripts.slp1 == "paT"
