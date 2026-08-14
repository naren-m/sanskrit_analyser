import asyncio

import pytest

from sanskrit_analyzer import Analyzer, AnalysisMode
from sanskrit_analyzer.config import Config


@pytest.fixture(scope="module")
def az():
    # Disable persistent caches so the test exercises the live segmentation
    # path rather than a stale cached result.
    config = Config()
    config.cache.redis_enabled = False
    config.cache.sqlite_enabled = False
    return Analyzer(config)


def _words(tree):
    return [
        w
        for p in tree.parse_forest[:1]
        for sg in p.sandhi_groups
        for w in sg.base_words
    ]


def test_simple_sentence_is_segmented(az):
    tree = asyncio.run(az.analyze("स गच्छति वनम्", mode=AnalysisMode.EDUCATIONAL))
    words = _words(tree)
    assert len(words) >= 3, (
        f"expected >=3 words, got {[w.surface_form for w in words]}"
    )


def test_verb_carries_dhatu(az):
    tree = asyncio.run(az.analyze("स गच्छति वनम्", mode=AnalysisMode.EDUCATIONAL))
    roots = {w.dhatu.dhatu for w in _words(tree) if getattr(w, "dhatu", None)}
    assert "gam" in roots
