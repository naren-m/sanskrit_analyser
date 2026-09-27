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
from tests._cases import check_cases


def test_canonical_key() -> None:
    cases = [
        # राम (stem), रामः (nom.), रामं (acc.) and 'Rama' collapse to one key.
        ("stem", "राम", "rama"),
        ("visarga_nominative", "रामः", "rama"),
        ("anusvara_accusative", "रामं", "rama"),
        ("english_iast_spelling", "Rama", "rama"),
        ("empty", "", ""),
        # Without Brahmic normalisation the Gujarati વ/ા are dropped by the
        # Devanagari→IAST transliteration, shortening the key to "visamitra": a
        # different length, so is_near_spelling_variant's equal-length guard
        # can never rescue it (ramayanam#419).
        ("ramayanam_419_mixed_brahmic_folds", "विश્વामित्र", canonical_key("विश्वामित्र")),
    ]

    def check(text, expected):
        assert canonical_key(text) == expected

    check_cases(cases, check)
    assert canonical_key("नारद") != canonical_key("राम"), "distinct names stay distinct"


def test_fold_virama() -> None:
    cases = [
        ("drops_trailing_inherent_a", "hanumana", "hanuman"),
        ("folds_above_3_char_floor", "rama", "ram"),
        # The length floor (len > 3) protects genuinely short keys from being gutted.
        ("short_key_protected", "aja", "aja"),
    ]

    def check(key, expected):
        assert fold_virama(key) == expected

    check_cases(cases, check)


def test_keys_match() -> None:
    # हनुमान् (hanumān) and हनुमान (hanumāna) differ only by a trailing halant:
    # the canonical keys genuinely differ but fold to the same entity.
    assert canonical_key("हनुमान्") != canonical_key("हनुमान")
    real = "विश्वामित्र"
    cases = [
        ("trailing_halant_folds", "हनुमान्", "हनुमान", True),
        # The three corrupted spellings that reached the Ramayanam KG index.
        ("kg_corruption_single_char_ra_for_va", real, "विश्रामित्र", True),
        ("kg_corruption_gujarati_splice", real, "विश્વामित्र", True),
        ("kg_corruption_mixed_latin", real, "Vइस्टमित्र", True),
        ("short_distinct_names", "राम", "रावण", False),
        ("distinct_names", "नारद", "राम", False),
        ("equal_keys_still_match", "राम", "रामः", True),
    ]

    def check(a, b, expected):
        assert keys_match(canonical_key(a), canonical_key(b)) is expected

    check_cases(cases, check)


def test_is_near_spelling_variant() -> None:
    cases = [
        ("one_interior_substitution", "visvamitra", "visramitra", True),
        ("too_short_protects_rama_kama", "rama", "kama", False),
        ("leading_difference_not_interior", "aardvark", "bardvark", False),
        ("length_change_not_a_variant", "laksmana", "laksana", False),
    ]

    def check(a, b, expected):
        assert is_near_spelling_variant(a, b) is expected

    check_cases(cases, check)
