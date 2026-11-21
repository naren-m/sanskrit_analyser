"""Candidate-analysis gating for the kosha engine (particles, proper nouns)."""

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
