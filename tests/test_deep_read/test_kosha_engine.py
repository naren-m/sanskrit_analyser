"""Candidate-analysis gating for the kosha engine (particles, proper nouns)."""

import json
from pathlib import Path

import pytest

from sanskrit_analyzer.deep_read import kosha_engine as engine
from sanskrit_analyzer.deep_read.kosha_engine import Analysis

requires_vidyut = pytest.mark.skipif(
    not engine.is_available(), reason="vidyut data bundle not present"
)


def _verb(lemma):
    return Analysis(kind="verb", lemma=lemma,
                    dhatu=engine.DhatuView(root=lemma))


def _kinds(analyses):
    return [a.kind for a in analyses]


# (slp, candidates, fake vidyut readings, expected kinds, expected lemma of lead)
GATE_CASES = {
    "particle drops verb and nominal": (
        "ca", ["ca"],
        [_verb("ci"), Analysis(kind="nominal", lemma="ca"),
         Analysis(kind="indeclinable", lemma="ca")],
        ["indeclinable"], "ca"),
    "particle without avyaya entry is synthesized": (
        "tu", ["tu"], [_verb("tu")], ["indeclinable"], "tu"),
    "visarga particle matches surface form": (
        "punaH", ["punar"], [_verb("pu")], ["indeclinable"], "punaH"),
    "proper noun drops verb, nominal leads": (
        "rAmo", ["rAmaH", "rAma"],
        [_verb("ra"), Analysis(kind="derived", lemma="rAma"),
         Analysis(kind="nominal", lemma="rAma")],
        ["nominal", "derived"], "rAma"),
    "proper noun matched by candidate gets synthesized nominal": (
        "sItAyAH", ["sItA"], [_verb("sI")], ["nominal"], "sItA"),
    "ordinary word keeps verb-first order": (
        "gacCati", ["gacCati"],
        [Analysis(kind="nominal", lemma="gam"), _verb("gam")],
        ["verb", "nominal"], "gam"),
    "maha leads with nominal mahat, mahi stays alternate": (
        "mahA", ["mahA", "maha"],
        [Analysis(kind="derived", lemma="mahi"), Analysis(kind="nominal", lemma="mahA")],
        ["nominal", "derived", "nominal"], "mahat"),
    "maha reuses an existing mahat reading": (
        "maha", ["maha"],
        [Analysis(kind="derived", lemma="mahi"), Analysis(kind="nominal", lemma="mahat")],
        ["nominal", "derived"], "mahat"),
    "tie within a kind keeps lookup order, not lemma votes": (
        "xa", ["xa"],
        [Analysis(kind="nominal", lemma="aa"), Analysis(kind="nominal", lemma="zz"),
         Analysis(kind="nominal", lemma="zz", morphology={"vibhakti": "praTamA"})],
        ["nominal", "nominal", "nominal"], "aa"),
    "kind order beats lookup order": (
        "xa", ["xa"],
        [Analysis(kind="nominal", lemma="n"), Analysis(kind="nominal", lemma="n",
                                                       morphology={"vibhakti": "praTamA"}),
         Analysis(kind="derived", lemma="d")],
        ["derived", "nominal", "nominal"], "d"),
    "full tie keeps lookup order": (
        "xa", ["xa"],
        [Analysis(kind="nominal", lemma="b"), Analysis(kind="nominal", lemma="a")],
        ["nominal", "nominal"], "b"),
}


@pytest.mark.parametrize("case", GATE_CASES, ids=list(GATE_CASES))
def test_gate_and_rank(case):
    slp, candidates, readings, kinds, lead = GATE_CASES[case]
    out = engine._gate_and_rank(readings, slp, candidates)
    assert _kinds(out) == kinds
    assert out[0].lemma == lead


def test_mark_primary_flags_only_first():
    out = engine._mark_primary([Analysis(kind="verb"), Analysis(kind="nominal")])
    assert [d["primary"] for d in out] == [True, False]


@requires_vidyut
def test_ramo_is_nominal_primary_without_verb_root():
    res = engine.analyze_word("रामो")
    first = res["analyses"][0]
    assert first["kind"] == "nominal" and first["primary"] is True
    assert all(a["kind"] != "verb" for a in res["analyses"])


@requires_vidyut
def test_ca_resolves_to_indeclinable_only():
    res = engine.analyze_word("च")
    assert [a["kind"] for a in res["analyses"]] == ["indeclinable"]
    assert res["analyses"][0]["primary"] is True


@requires_vidyut
def test_finite_verb_still_leads_for_ordinary_word():
    res = engine.analyze_word("गच्छति")
    assert res["analyses"][0]["kind"] == "verb"
    assert [a["primary"] for a in res["analyses"]][:1] == [True]


_SURFACE_FORMS = json.loads((Path(__file__).parent / "surface_forms.json").read_text("utf-8"))


@requires_vidyut
@pytest.mark.parametrize("row", _SURFACE_FORMS["resolves"], ids=lambda r: r["form"])
def test_surface_form_resolves(row):
    analyses = engine.analyze_word(row["form"])["analyses"]
    # rows marked "primary" must be the lead reading; others may be any reading
    pool = analyses[:1] if row.get("primary") else analyses
    assert any(
        a["kind"] == row["kind"]
        and a["lemma"] == row.get("lemma", a["lemma"])
        and (a["dhatu"] or {}).get("root") == row.get("root", (a["dhatu"] or {}).get("root"))
        and a["morphology"].get("lakara") == row.get("lakara", a["morphology"].get("lakara"))
        for a in pool)


@requires_vidyut
@pytest.mark.parametrize("form", _SURFACE_FORMS["unresolved"])
def test_surface_form_stays_unresolved(form):
    assert engine.analyze_word(form)["resolved"] is False


@requires_vidyut
def test_epic_present_is_marked_variant():
    lead = engine.analyze_word("प्रच्छति")["analyses"][0]
    assert "pfcCati" in lead["variant"]


# (input, expected Devanagari tokens). IAST and SLP1 lines used to tokenize to
# [] because tokens were only ever trimmed to a Devanagari run.
TOKENIZE_CASES = {
    "devanagari": ("रामो गच्छति वनम्॥", ["रामो", "गच्छति", "वनम्"]),
    "iast": ("rāmo gacchati vanam", ["रामो", "गच्छति", "वनम्"]),
    "slp1": ("rAmo gacCati vanam", ["रामो", "गच्छति", "वनम्"]),
    "iast-verse-ref-dropped": ("rāmo nāma ||1.1.8||", ["रामो", "नाम"]),
    "empty": ("", []),
}


@pytest.mark.parametrize("case", TOKENIZE_CASES, ids=list(TOKENIZE_CASES))
def test_tokenize(case):
    text, want = TOKENIZE_CASES[case]
    assert engine.tokenize(text) == want
