"""Tests for script/case-folded entity keys (issue #393).

Lifted from the Ramayanam knowledge-graph reader (#345/#352). The assertions
mirror the originals so the shared implementation is a faithful lift that other
scripture apps (Yoga Sutras, ...) can rely on.
"""
from __future__ import annotations

import pytest

from sanskrit_analyzer import vidyut_data
from sanskrit_analyzer.utils.entity_keys import (
    canonical_key,
    fold_virama,
    is_near_spelling_variant,
    keys_match,
    lemma_keys,
    lemma_keys_match,
)


def test_canonical_key_merges_script_and_case_variants():
    """राम (stem), रामः (nom.), रामं (acc.) and 'Rama' collapse to one key."""
    key = canonical_key("राम")
    assert key == "rama"
    assert canonical_key("रामः") == key  # visarga nominative
    assert canonical_key("रामं") == key  # anusvara accusative
    assert canonical_key("Rama") == key  # English/IAST spelling


def test_canonical_key_keeps_distinct_names_distinct():
    assert canonical_key("नारद") != canonical_key("राम")


def test_canonical_key_empty():
    assert canonical_key("") == ""


def test_fold_virama_drops_trailing_inherent_a():
    assert fold_virama("hanumana") == "hanuman"
    # Keys longer than the 3-char floor fold their trailing inherent 'a'.
    assert fold_virama("rama") == "ram"
    # The length floor (len > 3) protects genuinely short keys from being gutted.
    assert fold_virama("aja") == "aja"


def test_keys_match_folds_trailing_halant():
    """हनुमान् (hanumān) and हनुमान (hanumāna) split only by a trailing halant."""
    a = canonical_key("हनुमान्")
    b = canonical_key("हनुमान")
    assert a != b  # canonical keys genuinely differ ...
    assert keys_match(a, b)  # ... but fold to the same entity.


def test_keys_match_collapses_single_char_misspelling():
    a = canonical_key("विश्वामित्र")
    b = canonical_key("विश्रामित्र")
    assert keys_match(a, b)


def test_canonical_key_folds_mixed_brahmic_spelling():
    """A name with sibling-script characters spliced in keys identically.

    Without Brahmic normalisation the Gujarati ``વ``/``ા`` are dropped by the
    Devanagari→IAST transliteration, shortening the key to ``visamitra`` — a
    different length, so :func:`is_near_spelling_variant`'s equal-length guard
    can never rescue it (ramayanam#419).
    """
    assert canonical_key("विश્વामित्र") == canonical_key("विश्वामित्र")


def test_keys_match_collapses_all_vishvamitra_corruptions():
    """The three corrupted spellings that reached the Ramayanam KG index."""
    real = canonical_key("विश्वामित्र")
    for corrupted in ("विश्रामित्र", "विश્વामित्र", "Vइस्टमित्र"):
        assert keys_match(real, canonical_key(corrupted)), corrupted


def test_keys_match_is_conservative_for_short_and_distinct_names():
    assert not keys_match(canonical_key("राम"), canonical_key("रावण"))
    assert not keys_match(canonical_key("नारद"), canonical_key("राम"))
    # Exactly-equal keys still match (script/case variants).
    assert keys_match(canonical_key("राम"), canonical_key("रामः"))


def test_is_near_spelling_variant_guards():
    # One interior substitution on long-enough keys -> variant.
    assert is_near_spelling_variant("visvamitra", "visramitra")
    # Too short -> never a variant (protects rama/kama/etc.).
    assert not is_near_spelling_variant("rama", "kama")
    # A leading/trailing difference is not an interior variant.
    assert not is_near_spelling_variant("aardvark", "bardvark")
    # Different lengths (insertion/deletion) -> not a variant.
    assert not is_near_spelling_variant("laksmana", "laksana")


# (id, name_a, name_b, same entity?) — #33. The ids say what each row proves.
LEMMA_MATCH_CASES = [
    ("vowel length separates king Sagara from the ocean", "सगर", "सागर", False),
    ("instrumental keeps the king's stem", "सगर", "सगरेण", True),
    ("accusative folds onto the stem", "सागर", "सागरम्", True),
    ("visarga nominative is looked up as final s", "सागर", "सागरः", True),
    ("genitive folds onto the stem", "सागरम्", "सागरस्य", True),
    ("final anusvara equals final m", "भयम्", "भयं", True),
    ("mid-word anusvara equals the class nasal", "स्वयम्भू", "स्वयंभु", True),
    ("singular and plural share a stem", "वानरः", "वानराः", True),
    ("visarga sandhi -o is also read as -as", "हरयो", "हरि", True),
    ("a participle root does not join hara and hAra", "हर", "हार", False),
    ("mountain is not serpent", "नागः", "नगाः", False),
    ("arm is not many", "बाहुभिः", "बहुभिः", False),
    ("conduct is not rock", "शील", "शिला", False),
    ("gender pair merges by default", "रम्भ", "रम्भा", True),
    ("IAST input reaches the same stem", "sāgaram", "सागर", True),
    ("a name with no kosha entry never matches", "हरियूथपः", "हरियूथपाः", False),
    ("empty input never matches", "", "राम", False),
]


def test_lemma_keys():
    """Stem keys keep vowel length and fold case endings (#33).

    A new function, not a row in an existing table: this is the only test here
    that needs the vidyut kosha data, so it carries its own skip.
    """
    if not vidyut_data.is_available():
        pytest.skip("vidyut kosha data not available")
    failures = [
        f"{case_id}: {a} vs {b} -> {got}, want {want}"
        for case_id, a, b, want in LEMMA_MATCH_CASES
        if (got := lemma_keys_match(a, b)) != want
    ]
    assert lemma_keys("सागरस्य") == frozenset({"sAgara"})
    assert lemma_keys("रम्भ", prefer_exact=True) == frozenset({"ramBa"})
    assert not lemma_keys_match("रम्भ", "रम्भा", prefer_exact=True)
    assert not failures, "\n".join(failures)
