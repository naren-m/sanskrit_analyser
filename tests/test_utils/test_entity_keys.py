"""Tests for script/case-folded entity keys (issue #393).

Lifted from the Ramayanam knowledge-graph reader (#345/#352). The assertions
mirror the originals so the shared implementation is a faithful lift that other
scripture apps (Yoga Sutras, ...) can rely on.
"""
from __future__ import annotations

from sanskrit_analyzer.utils.entity_keys import (
    canonical_key,
    fold_virama,
    is_near_spelling_variant,
    keys_match,
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
