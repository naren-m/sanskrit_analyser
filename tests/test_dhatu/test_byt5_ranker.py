"""Tests for the optional ByT5 reranker/segmenter layer.

The model is heavy (~2 GB) and may be absent in CI, so the model-backed tests
skip when ByT5 is unavailable. The adapter's graceful-degradation contract is
tested without the model.
"""

from __future__ import annotations

import pytest

from sanskrit_analyzer.dhatu.byt5_ranker import ByT5Adapter


class _FakeSeg:
    def __init__(self, surface, pos):
        self.surface = surface
        self.pos = pos


class _FakeResult:
    def __init__(self, segments):
        self.segments = segments


class _FakeEngine:
    """Stand-in ByT5 engine so adapter logic is testable without the 2GB model."""

    is_available = True

    async def analyze(self, text):
        return _FakeResult([_FakeSeg("rāmaḥ", "noun"), _FakeSeg("gacchati", "verb")])


def test_adapter_segment_and_pos_hint_with_fake_engine():
    adapter = ByT5Adapter(engine=_FakeEngine())
    assert adapter.is_available()
    assert adapter.segment("रामः गच्छति") == ["rāmaḥ", "gacchati"]
    assert adapter.pos_hint("rāmaḥ") == "noun"
    assert adapter.pos_hint("gacchati") == "verb"
    assert adapter.pos_hint("unseen") is None


def test_adapter_segment_empty():
    assert ByT5Adapter(engine=_FakeEngine()).segment("") == []


# --- model-backed (skips without the cached ByT5) ------------------------------

def _byt5_available() -> bool:
    try:
        return ByT5Adapter().is_available()
    except Exception:
        return False


_needs_byt5 = pytest.mark.skipif(
    not _byt5_available(), reason="ByT5 model not available"
)


@_needs_byt5
def test_byt5_segments_real_compound():
    members = ByT5Adapter().segment("इक्ष्वाकुवंशप्रभवो रामो नाम जनैः श्रुतः")
    assert members is not None
    assert any("ikṣvāku" in m for m in members)
    assert any("vaṃśa" in m for m in members)


@_needs_byt5
def test_identifier_with_byt5_resolves_roots():
    from sanskrit_analyzer.dhatu import DhatuIdentifier

    results = DhatuIdentifier.with_byt5().identify("श्रुतः")
    roots = {(r.dhatu or {}).get("root") for r in results}
    assert "Sru" in roots
