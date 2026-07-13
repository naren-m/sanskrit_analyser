"""Tests for the generic dhātu identifier and its ranking layer."""

from __future__ import annotations

import pytest

from sanskrit_analyzer.dhatu import DhatuIdentifier
from sanskrit_analyzer.dhatu.identifier import rank_analyses
from sanskrit_analyzer.deep_read import kosha_engine


# --- ranking: pure, no vidyut data needed --------------------------------------

def _verb(root):
    return {"kind": "verb", "lemma": root, "dhatu": {"root": root}, "morphology": {}}


def _nominal(lemma):
    return {"kind": "nominal", "lemma": lemma, "dhatu": None, "morphology": {}}


def test_rank_demotes_short_root_verb_when_nominal_exists():
    # रामः-style: a 2-char-root finite verb must fall below an available nominal.
    ranked = rank_analyses([_verb("rA"), _nominal("rAma")])
    assert ranked[0]["kind"] == "nominal"


def test_rank_keeps_long_root_verb_first():
    # गच्छति-style: √gam (3 chars) stays verb-first even with a nominal present.
    ranked = rank_analyses([_verb("gam"), _nominal("gama")])
    assert ranked[0]["kind"] == "verb"


def test_rank_pos_hint_noun_floats_nominal():
    ranked = rank_analyses([_verb("gam"), _nominal("gama")], pos_hint="noun")
    assert ranked[0]["kind"] == "nominal"


def test_rank_pos_hint_verb_floats_verb():
    ranked = rank_analyses([_nominal("rAma"), _verb("rA")], pos_hint="verb")
    assert ranked[0]["kind"] == "verb"


def test_rank_empty():
    assert rank_analyses([]) == []


# --- identify: needs the vidyut data bundle ------------------------------------

_needs_data = pytest.mark.skipif(
    not kosha_engine.is_available(),
    reason="vidyut data bundle not available",
)


@_needs_data
def test_identify_empty():
    assert DhatuIdentifier().identify("") == []


@_needs_data
def test_identify_verb_root():
    results = DhatuIdentifier().identify("गच्छति")
    assert len(results) == 1
    assert (results[0].dhatu or {}).get("root") == "gam"


@_needs_data
def test_identify_perfect_resolves_to_root():
    results = DhatuIdentifier().identify("जगाम")
    assert (results[0].dhatu or {}).get("root") == "gam"


@_needs_data
def test_identify_splits_compound_and_identifies_members():
    results = DhatuIdentifier().identify("इक्ष्वाकुवंशप्रभवो रामो नाम जनैः श्रुतः")
    # the fused compound expanded into >= 7 padas
    assert len(results) >= 7
    # the participle श्रुतः is lemmatized to its root √śru
    roots = {(r.dhatu or {}).get("root") for r in results}
    assert "Sru" in roots


@_needs_data
def test_identify_rama_not_spurious_finite_verb():
    # रामः must not be top-ranked as a bare short-root finite verb (√rā).
    results = DhatuIdentifier().identify("रामः")
    top = results[0].analyses[0]
    assert top["kind"] != "verb" or len((top.get("dhatu") or {}).get("root") or "") > 2
