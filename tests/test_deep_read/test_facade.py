"""Orchestration tests for the DeepRead facade.

Offline/deterministic: the Dharmamitra path is disabled (``use_dharmamitra=
False``) so these never touch the external API. Vidyut-backed assertions skip
when the data bundle is absent.
"""

import pytest

from sanskrit_analyzer import DeepRead, DeepReadResult
from sanskrit_analyzer.deep_read import kosha_engine as engine
from sanskrit_analyzer.dhatu.resolver import get_dhatu_resolver

requires_vidyut = pytest.mark.skipif(
    not engine.is_available(), reason="vidyut data bundle not present"
)

requires_resolver = pytest.mark.skipif(
    not get_dhatu_resolver()._ensure(),
    reason="vidyut data bundle not available for DhatuResolver",
)


def test_analyze_returns_typed_result():
    dr = DeepRead()
    res = dr.analyze("रामः", use_dharmamitra=False)
    assert isinstance(res, DeepReadResult)
    assert res.engine in ("vidyut-kosha", "sanskrit-analyzer")


def test_analyze_to_dict_shape():
    dr = DeepRead()
    out = dr.analyze("रामः", use_dharmamitra=False).to_dict()
    assert set(out) >= {"input", "slp1", "engine", "tokens", "notes"}
    assert isinstance(out["tokens"], list) and len(out["tokens"]) == 1
    tok = out["tokens"][0]
    assert {"surface", "slp1", "resolved", "analyses"} <= set(tok)
    assert isinstance(tok["analyses"], list) and tok["analyses"]
    assert {"kind", "lemma", "dhatu", "morphology"} <= set(tok["analyses"][0])
    assert out["notes"]  # honesty notes are present


def test_analyze_empty():
    dr = DeepRead()
    out = dr.analyze("", use_dharmamitra=False).to_dict()
    assert out["tokens"] == []


@requires_vidyut
def test_running_text_verse_keeps_padas_whole():
    # A real running-text verse: the local kosha+de-sandhi engine keeps padas
    # intact and honestly leaves true samāsa/glued padas unresolved.
    verse = (
        "इक्ष्वाकुवंशप्रभवो रामो नाम जनैश्श्रुतः "
        "नियतात्मा महावीर्यो द्युतिमान्धृतिमान् वशी"
    )
    out = DeepRead().analyze(verse, use_dharmamitra=False).to_dict()
    by_surface = {t["surface"]: t for t in out["tokens"]}
    assert len(out["tokens"]) == 8
    assert by_surface["नियतात्मा"]["analyses"][0]["lemma"] == "niyatAtman"
    assert by_surface["महावीर्यो"]["analyses"][0]["lemma"] == "mahAvIrya"
    assert by_surface["रामो"]["resolved"] is True
    assert by_surface["इक्ष्वाकुवंशप्रभवो"]["resolved"] is False


@requires_vidyut
def test_verb_shows_dhatu():
    out = DeepRead().analyze("स गच्छति वनम्", use_dharmamitra=False).to_dict()
    roots = {
        a["dhatu"]["root"]
        for t in out["tokens"]
        for a in t["analyses"]
        if a.get("dhatu")
    }
    assert "gam" in roots, f"roots seen: {roots} (engine={out['engine']})"


@requires_resolver
def test_analyze_via_segmenter_resolves_clean_root():
    # योगः must resolve to the clean root yuj through the shared DhatuResolver,
    # matching DhatuIdentifier().identify(). Before the fix the facade returned
    # the Kośa's raw "yoji" anubandha residue, so the two public APIs disagreed.
    out = DeepRead().analyze_via_segmenter("योगः").to_dict()
    roots = [
        a["dhatu"]["root"]
        for t in out["tokens"]
        for a in t["analyses"]
        if a.get("dhatu")
    ]
    assert "yuj" in roots
    assert "yoji" not in roots


def test_via_dharmamitra_returns_none_when_disabled_input_empty():
    # Empty input short-circuits to None without any network call.
    assert DeepRead().analyze_via_dharmamitra("") is None


@requires_vidyut
def test_via_analyzer_typed_or_none():
    # The Analyzer path returns a typed result or None (never raises). We only
    # assert the contract, not quality (quality is tracked, not gated).
    res = DeepRead().analyze_via_analyzer("रामः")
    assert res is None or isinstance(res, DeepReadResult)


def test_analyze_degrades_when_vidyut_unavailable(monkeypatch):
    # Dharmamitra disabled AND the vidyut bundle absent: analyze() must degrade
    # to unknown-token output instead of raising VidyutUnavailable.
    def boom(word):
        raise engine.VidyutUnavailable("vidyut data bundle not present")

    monkeypatch.setattr(engine, "analyze_word", boom)

    out = DeepRead().analyze("रामो नाम", use_dharmamitra=False).to_dict()
    assert out["engine"] == "unavailable"
    assert out["tokens"]  # segmentation still produced tokens
    assert all(t["resolved"] is False for t in out["tokens"])
    assert all(t["analyses"][0]["kind"] == "unknown" for t in out["tokens"])
    assert out["notes"]


def test_analyze_sloka_sync_works_in_running_loop():
    # Inside a running event loop, _analyze_sloka_sync must not raise the
    # "asyncio.run() cannot be called from a running event loop" error.
    import asyncio

    class _FakeAnalyzer:
        async def analyze(self, text, mode=None):
            return f"analyzed:{text}"

    dr = DeepRead()
    dr._analyzer = _FakeAnalyzer()

    async def driver():
        return dr._analyze_sloka_sync("रामः", mode=None)

    assert asyncio.run(driver()) == "analyzed:रामः"
