"""Tests for the generic dhātu identifier and its ranking layer."""

from __future__ import annotations

import pytest

from sanskrit_analyzer.deep_read import kosha_engine
from sanskrit_analyzer.dhatu import DhatuIdentifier
from sanskrit_analyzer.dhatu.identifier import rank_analyses
from sanskrit_analyzer.dhatu.resolver import get_dhatu_resolver
from tests._cases import check_cases

# --- ranking: pure, no vidyut data needed --------------------------------------

def _verb(root):
    return {"kind": "verb", "lemma": root, "dhatu": {"root": root}, "morphology": {}}


def _nominal(lemma):
    return {"kind": "nominal", "lemma": lemma, "dhatu": None, "morphology": {}}


# (row id, analyses, pos_hint, expected kind of the top analysis)
RANK_CASES = [
    # रामः-style: a 2-char-root finite verb must fall below an available nominal.
    ("short-root-verb-demoted-below-nominal", [_verb("rA"), _nominal("rAma")], None, "nominal"),
    # गच्छति-style: √gam (3 chars) stays verb-first even with a nominal present.
    ("long-root-verb-stays-first", [_verb("gam"), _nominal("gama")], None, "verb"),
    ("pos-hint-noun-floats-nominal", [_verb("gam"), _nominal("gama")], "noun", "nominal"),
    ("pos-hint-verb-floats-verb", [_nominal("rAma"), _verb("rA")], "verb", "verb"),
]


def test_rank_analyses():
    def check(analyses, pos_hint, kind):
        assert rank_analyses(analyses, pos_hint=pos_hint)[0]["kind"] == kind

    check_cases(RANK_CASES, check)
    assert rank_analyses([]) == []


# --- identify: needs the vidyut data bundle ------------------------------------

_needs_data = pytest.mark.skipif(
    not kosha_engine.is_available(),
    reason="vidyut data bundle not available",
)


@_needs_data
def test_identify():
    assert DhatuIdentifier().identify("") == []

    results = DhatuIdentifier().identify("गच्छति")
    assert len(results) == 1
    assert (results[0].dhatu or {}).get("root") == "gam"

    # the perfect resolves to its root
    results = DhatuIdentifier().identify("जगाम")
    assert (results[0].dhatu or {}).get("root") == "gam"

    results = DhatuIdentifier().identify("इक्ष्वाकुवंशप्रभवो रामो नाम जनैः श्रुतः")
    # the fused compound expanded into >= 7 padas
    assert len(results) >= 7
    # the participle श्रुतः is lemmatized to its root √śru
    roots = {(r.dhatu or {}).get("root") for r in results}
    assert "Sru" in roots

    # रामः must not be top-ranked as a bare short-root finite verb (√rā).
    results = DhatuIdentifier().identify("रामः")
    top = results[0].analyses[0]
    assert top["kind"] != "verb" or len((top.get("dhatu") or {}).get("root") or "") > 2


# --- identify: delegates to DhatuResolver for the actual root ------------------

_needs_resolver = pytest.mark.skipif(
    not get_dhatu_resolver()._ensure(),
    reason="vidyut data bundle not available for DhatuResolver",
)

# (row id, word, root that must be among the identified roots)
RESOLVED_ROOT_CASES = [
    # योगः must resolve to the clean root yuj, not the Kośa's raw yoji residue.
    ("yoga-clean-root-not-anubandha-residue", "योगः", "yuj"),
    # अनुशासनम् is filed by the Kośa as a plain, unlinked nominal; the resolver
    # peels the anu- upasarga and resolves the remainder to √śās.
    ("anuSAsana-peels-upasarga", "अनुशासनम्", "SAs"),
    # hānam is 'abandonment' (√hā), not 'killing' (√han).
    ("hAnam-prefers-hA-over-han", "हानम्", "hA"),
]


@_needs_resolver
def test_identify_resolves_roots():
    def check(word, root):
        roots = [r.dhatu["root"] for r in DhatuIdentifier().identify(word) if r.dhatu]
        assert root in roots, roots

    check_cases(RESOLVED_ROOT_CASES, check)
    roots = [r.dhatu["root"] for r in DhatuIdentifier().identify("हानम्") if r.dhatu]
    assert roots[0] != "han"


@_needs_resolver
def test_preferred_root_hook_settles_a_homograph():
    """The hook is meant for a dictionary keyed by stem/lemma, so it must be
    called with the SLP1 *lemma* (here the stem "rAga", which the ranker puts
    first for रागः since #572 — before that it was the causative-root reading
    "rAgi"), not the inflected surface ("rAgaH", with its visarga). A hook
    that only ever sees inflected surfaces would miss on every stem-keyed
    dictionary lookup, defeating its purpose."""
    received: list[str] = []

    def preferred_root_fn(w: str) -> str | None:
        received.append(w)
        return "raYj"

    ident = DhatuIdentifier(preferred_root_fn=preferred_root_fn)
    results = ident.identify("रागः")

    assert received == ["rAga"], (
        f"hook must receive the SLP1 lemma, not the inflected surface; got {received!r}"
    )
    assert any(r.dhatu and r.dhatu["root"] == "raYj" for r in results)


def _derived(root, krt):
    return {"kind": "derived", "lemma": root, "dhatu": {"root": root},
            "morphology": {}, "krt": krt}


def _avyaya(lemma):
    return {"kind": "indeclinable", "lemma": lemma, "dhatu": None, "morphology": {}}


# (id, candidates in kosha order, expected top lemma). Each row is a word the
# reader showed with the wrong root before #572; kosha order is kept verbatim.
RANK_CASES = [
    ("ca-avyaya-beats-kvip-root-noun",
     [_derived("ci", "kvi~p"), _derived("capi", "kvi~p"), _nominal("ca"), _avyaya("ca")],
     "ca"),
    ("tatas-avyaya-beats-participle-of-tan",
     [_derived("tan", "kta"), _nominal("tata"), _avyaya("tatas")], "tatas"),
    ("sa-pronoun-beats-kvip-and-saman",
     [_derived("sAvi", "kvi~p"), _nominal("sAman"), _nominal("sA"), _nominal("tad")], "tad"),
    ("tasya-pronoun-beats-imperative-of-tas",
     [_verb("tas"), _nominal("tad"), _nominal("ta")], "tad"),
    ("vakyam-stem-beats-root-lemma",
     [_derived("vac", "Ryat"), _nominal("vAkya")], "vAkya"),
    ("vanam-stem-beats-kvip-of-van",
     [_derived("vAni", "kvi~p"), _derived("van", "kvi~p"), _nominal("vana")], "vana"),
    ("krtva-gerund-beats-krtvan-noun",
     [_nominal("kftvan"), _derived("kf", "ktvA")], "kf"),
    ("gatah-participle-beats-kvip",
     [_derived("gam", "kvi~p"), _derived("gam", "kta")], "gam"),
]


def test_rank_reading_order_table():
    """Fallback reading order, one row per word class the reader got wrong (#572)."""
    failures = []
    for case_id, candidates, want in RANK_CASES:
        got = rank_analyses(list(candidates))[0]["lemma"]
        if got != want:
            failures.append(f"{case_id}: top lemma {got!r}, want {want!r}")
    assert not failures, "\n".join(failures)
