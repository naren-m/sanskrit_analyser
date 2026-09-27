"""Unit tests for the Deep Read kosha dhātu engine.

Pure-helper tests always run. The vidyut-backed tests are skipped automatically
if the data bundle is absent, so the suite is green on a machine without it.
(Ported from ramayanam ``tests/unit/test_deep_read_engine.py`` during the
deep-read promotion — see naren-m/sanskrit_analyser#8.)
"""

import pytest

from sanskrit_analyzer.deep_read import kosha_engine as engine
from tests._cases import check_cases

requires_vidyut = pytest.mark.skipif(
    not engine.is_available(), reason="vidyut data bundle not present"
)


# --------------------------- pure helpers ---------------------------------

# (row id, helper, input, expected output)
HELPER_CASES = [
    # slp / to_iast / to_devanagari are public (the user-facing amendment).
    ("slp-transliterates-devanagari", engine.slp, "रामः", "rAmaH"),
    ("to-devanagari-none", engine.to_devanagari, None, None),
    ("to-iast-none", engine.to_iast, None, None),
    ("to-devanagari-slp1", engine.to_devanagari, "gam", "गम्"),
    ("tokenize-splits-on-whitespace", engine.tokenize,
     "रामो विग्रहवान् धर्मः", ["रामो", "विग्रहवान्", "धर्मः"]),
    ("tokenize-strips-dandas-and-punctuation", engine.tokenize,
     "गच्छति वनम्॥ राम।", ["गच्छति", "वनम्", "राम"]),
    # A ZWJ is outside the Devanagari run, so धर्म‍क्षेत्रे used to become धर्म.
    ("tokenize-drops-zwj-zwnj-inside-word", engine.tokenize,
     "धर्म‍क्षेत्रे कुरु‌क्षेत्रे", ["धर्मक्षेत्रे", "कुरुक्षेत्रे"]),
    ("tokenize-empty", engine.tokenize, "", []),
    ("tokenize-only-punctuation", engine.tokenize, "   ॥ ", []),
    # "।।1.1.8।।" must not leak "1 1 8" tokens.
    ("tokenize-drops-verse-reference-digits", engine.tokenize,
     "रामो नाम ।।1.1.8।।", ["रामो", "नाम"]),
    # Kosha stores -s/-r forms, not pausal -H. (rAmaH -> 0, rAmas -> many.)
    ("visarga-candidates-expand-terminal-visarga", engine.visarga_candidates,
     "rAmaH", ["rAmaH", "rAmas", "rAmar"]),
    ("visarga-candidates-passthrough", engine.visarga_candidates,
     "gacCati", ["gacCati"]),
    ("gana-bhvadi", engine.gana_to_number, "BvAdi", 1),
    ("gana-curadi", engine.gana_to_number, "curAdi", 10),
    # vidyut spells it ruDAdi; the old table had ruDadi, so gaṇa 7 was None.
    ("gana-ruDAdi-vidyut-spelling", engine.gana_to_number, "ruDAdi", 7),
    ("gana-unknown-spelling", engine.gana_to_number, "bhvadi", None),
    ("gana-none", engine.gana_to_number, None, None),
    ("english-curated-gam", engine.english_for_root, "gam", "to go"),
    ("english-unknown-root", engine.english_for_root, "nonexistent-root", None),
    ("english-none", engine.english_for_root, None, None),
]


def test_pure_helpers():
    def check(helper, arg, expected):
        assert helper(arg) == expected

    check_cases(HELPER_CASES, check)

    # Backward-compatible names must be the *same objects*, not copies.
    assert engine._slp is engine.slp
    assert engine._to_iast is engine.to_iast
    assert engine._to_devanagari is engine.to_devanagari

    # रामो in running text = रामः after visarga sandhi; must reach the -as/-a forms.
    cands = engine.desandhi_candidates("rAmo")
    assert "rAmas" in cands and "rAma" in cands
    # sibilant visarga sandhi is undone
    assert engine.desandhi_candidates("janES")[1:] == ["janEH", "janEs"]


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

    # कूजन्तम् -> participle derived from √kūj
    res = engine.analyze_word("कूजन्तम्")
    roots = {a["dhatu"]["root"] for a in res["analyses"] if a["dhatu"]}
    assert "kUj" in roots

    # gaṇa 7 through vidyut's real enum string, not a hand-typed name.
    res = engine.analyze_word("रुणद्धि")
    assert [a["dhatu"]["gana_num"] for a in res["analyses"] if a["dhatu"]] == [7]


# (row id, word) — each resolves only via a de-sandhi candidate
DESANDHI_CASES = [
    ("kosha-keys-rAmas-not-pausal-rAmaH", "रामः"),
    ("running-text-o-sandhi-of-rAmaH", "रामो"),
    ("anusvara-before-k-varga-kosha-keys-SaNkara", "शंकरः"),
    ("anusvara-before-g-kosha-keys-puNgava", "पुंगवम्"),
    ("anusvara-before-d-kosha-keys-candra", "चंद्रः"),
]


@requires_vidyut
def test_word_resolves_only_via_desandhi_candidate():
    def check(word):
        assert engine.analyze_word(word)["resolved"]

    check_cases(DESANDHI_CASES, check)


@requires_vidyut
def test_unresolved_words_degrade_gracefully():
    res = engine.analyze_word("इक्ष्वाकुवंशप्रभवो")
    assert res["resolved"] is False
    assert "compound" in res["reason"]

    res = engine.analyze_word("क्ष्क्ष्क्ष")
    assert res["resolved"] is False
    assert res["analyses"] == [{"kind": "unknown", "lemma": None,
                                "dhatu": None, "morphology": {}}]
