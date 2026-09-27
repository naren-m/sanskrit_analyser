"""Tests for Vidyut engine wrapper."""

import asyncio

import pytest

from sanskrit_analyzer.engines.vidyut_engine import VidyutEngine
from tests._cases import check_cases

# (id, input, min segments, lemma that must appear or None)
CASES = [
    ("SLP1 verb finds lemma gam", "gacCati", 1, "gam"),
    ("Devanagari input is analysed", "गच्छति", 1, None),
    ("IAST input is analysed", "gacchati", 1, None),
    # rāmo gacchati = rāmaḥ + gacchati (with sandhi)
    ("sandhi across two words yields two segments", "rAmo gacCati", 2, None),
]


@pytest.fixture
def engine() -> VidyutEngine:
    engine = VidyutEngine()
    if not engine.is_available:
        pytest.skip("Vidyut not available")
    return engine


def test_engine_name() -> None:
    assert VidyutEngine().name == "vidyut"


def test_analyze(engine: VidyutEngine) -> None:
    def check(text, min_segments, lemma):
        result = asyncio.run(engine.analyze(text))
        assert result.success
        assert result.engine == "vidyut"
        assert len(result.segments) >= min_segments, result.segments
        if lemma is not None:
            assert lemma in [seg.lemma for seg in result.segments]
        # Confidence is returned for the result and every segment.
        assert result.confidence > 0
        for seg in result.segments:
            assert seg.confidence > 0

    check_cases(CASES, check)

    # Empty input should not crash.
    assert asyncio.run(engine.analyze("")).engine == "vidyut"
