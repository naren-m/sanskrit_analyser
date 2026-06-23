"""Unit tests for the Deep Read kosha dhātu engine.

Pure-helper tests always run. The vidyut-backed tests are skipped automatically
if the data bundle is absent, so the suite is green on a machine without it.
(Ported from ramayanam ``tests/unit/test_deep_read_engine.py`` during the
deep-read promotion — see naren-m/sanskrit_analyser#8.)
"""

import pytest

from sanskrit_analyzer.deep_read import kosha_engine as engine

requires_vidyut = pytest.mark.skipif(
    not engine.is_available(), reason="vidyut data bundle not present"
)


# --------------------------- public helpers -------------------------------

def test_transliteration_helpers_are_public():
    # The user-facing amendment: slp / to_iast / to_devanagari are public.
    assert callable(engine.slp)
    assert callable(engine.to_iast)
    assert callable(engine.to_devanagari)


def test_underscore_aliases_alias_the_public_helpers():
    # Backward-compatible names must be the *same objects*, not copies.
    assert engine._slp is engine.slp
    assert engine._to_iast is engine.to_iast
    assert engine._to_devanagari is engine.to_devanagari


def test_slp_transliterates_devanagari():
    assert engine.slp("रामः") == "rAmaH"


def test_to_devanagari_and_to_iast_handle_none():
    assert engine.to_devanagari(None) is None
    assert engine.to_iast(None) is None
    assert engine.to_devanagari("gam") == "गम्"


# --------------------------- pure helpers ---------------------------------

def test_tokenize_splits_on_whitespace():
    assert engine.tokenize("रामो विग्रहवान् धर्मः") == ["रामो", "विग्रहवान्", "धर्मः"]


def test_tokenize_strips_dandas_and_punctuation():
    assert engine.tokenize("गच्छति वनम्॥ राम।") == ["गच्छति", "वनम्", "राम"]


def test_tokenize_empty():
    assert engine.tokenize("") == []
    assert engine.tokenize("   ॥ ") == []


def test_visarga_candidates_expands_terminal_visarga():
    # Kosha stores -s/-r forms, not pausal -H. (rAmaH -> 0, rAmas -> many.)
    assert engine.visarga_candidates("rAmaH") == ["rAmaH", "rAmas", "rAmar"]


def test_visarga_candidates_passthrough_when_no_visarga():
    assert engine.visarga_candidates("gacCati") == ["gacCati"]


def test_desandhi_undoes_o_sandhi():
    # रामो in running text = रामः after visarga sandhi; must reach the -as/-a forms.
    cands = engine.desandhi_candidates("rAmo")
    assert "rAmas" in cands and "rAma" in cands


def test_desandhi_undoes_sibilant_visarga():
    assert engine.desandhi_candidates("janES")[1:] == ["janEH", "janEs"]


def test_tokenize_drops_verse_reference_digits():
    # "।।1.1.8।।" must not leak "1 1 8" tokens.
    assert engine.tokenize("रामो नाम ।।1.1.8।।") == ["रामो", "नाम"]


def test_gana_to_number():
    assert engine.gana_to_number("BvAdi") == 1
    assert engine.gana_to_number("curAdi") == 10
    assert engine.gana_to_number("Gana.Bhvadi".split(".")[-1].lower()) is None  # unknown spelling
    assert engine.gana_to_number(None) is None


def test_english_for_root_curated_map():
    assert engine.english_for_root("gam") == "to go"
    assert engine.english_for_root("nonexistent-root") is None
    assert engine.english_for_root(None) is None


# ----------------------- vidyut-backed behavior ---------------------------

@requires_vidyut
def test_finite_verb_resolves_to_dhatu():
    res = engine.analyze_word("गच्छति")
    assert res["slp1"] == "gacCati"
    assert res["resolved"] is True
    roots = {a["dhatu"]["root"] for a in res["analyses"] if a["dhatu"]}
    assert "gam" in roots
    # at least one analysis is a finite verb (tinanta)
    assert any(a["kind"] == "verb" for a in res["analyses"])
    # the finite verb reading is presented first (most salient)
    assert res["analyses"][0]["kind"] == "verb"


@requires_vidyut
def test_participle_resolves_to_dhatu():
    # कूजन्तम् -> derived from √kūj
    res = engine.analyze_word("कूजन्तम्")
    roots = {a["dhatu"]["root"] for a in res["analyses"] if a["dhatu"]}
    assert "kUj" in roots


@requires_vidyut
def test_visarga_noun_resolves_via_candidate():
    # रामः (rAmaH) only resolves once we try the -s candidate.
    res = engine.analyze_word("रामः")
    assert res["resolved"] is True


@requires_vidyut
def test_sandhi_o_form_resolves_in_running_text():
    # रामो (running-text sandhi of रामः) must resolve after de-sandhi.
    res = engine.analyze_word("रामो")
    assert res["resolved"] is True


@requires_vidyut
def test_compound_gives_helpful_reason():
    res = engine.analyze_word("इक्ष्वाकुवंशप्रभवो")
    assert res["resolved"] is False
    assert "compound" in res["reason"]


@requires_vidyut
def test_unknown_word_degrades_gracefully():
    res = engine.analyze_word("क्ष्क्ष्क्ष")
    assert res["resolved"] is False
    assert res["analyses"] == [{"kind": "unknown", "lemma": None,
                                "dhatu": None, "morphology": {}}]
