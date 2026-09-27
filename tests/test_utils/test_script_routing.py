"""Tests for auto-detecting script routing (issue #393).

Lifted from the Ramayanam knowledge-graph reader (``text_hygiene``) so the
auto-detecting transliteration is shared across scripture apps. These pin the
same behaviour the Ramayanam tests asserted, proving the lift is faithful.
"""
from __future__ import annotations

from sanskrit_analyzer.utils.script_routing import (
    is_devanagari,
    normalize_brahmic,
    to_devanagari,
    to_iast,
)
from tests._cases import check_cases

# (id, function, input, expected)
ROUTING_CASES = [
    ("deva_from_slp1", to_devanagari, "rAmaH", "रामः"),
    ("deva_passes_through_devanagari", to_devanagari, "रामः", "रामः"),
    ("deva_empty_noop", to_devanagari, "", ""),
    # IAST must be detected as IAST, not blindly treated as SLP1. The old code
    # fed IAST to an SLP1->Deva transliteration: "yogaḥ" -> "योगḥ".
    ("deva_from_iast_keeps_visarga", to_devanagari, "yogaḥ", "योगः"),
    ("iast_from_devanagari", to_iast, "रामः", "rāmaḥ"),
    ("iast_passes_through_latin", to_iast, "Rama", "Rama"),
    # SLP1 is Latin-range, so the old is_devanagari() check let it pass
    # through undecoded: "yogaH" stayed "yogaH".
    ("iast_decodes_slp1", to_iast, "yogaH", "yogaḥ"),
    ("iast_empty_noop", to_iast, "", ""),
    ("is_deva_devanagari", is_devanagari, "राम", True),
    ("is_deva_latin", is_devanagari, "Rama", False),
    ("is_deva_slp1_is_latin_range", is_devanagari, "rAmaH", False),
    ("is_deva_empty", is_devanagari, "", False),
]


def test_script_routing() -> None:
    def check(fn, text, expected):
        assert fn(text) == expected

    check_cases(ROUTING_CASES, check)


MIXED = "विश્વामित्र"

# (id, input, expected) for normalize_brahmic — sibling-script folding
BRAHMIC_CASES = [
    # વ (U+0AB5) and ા (U+0ABE) sit at the same block offsets as व / ा.
    ("gujarati_folds", "વા", "वा"),
    # How one Viśvāmitra duplicate reached the Ramayanam KG (ramayanam#419):
    # visually identical, but two characters come from the Gujarati block.
    ("ramayanam_419_mixed_script_name", MIXED, "विश्वामित्र"),
    ("bengali_folds", "রাম", "राम"),
    ("telugu_folds", "రామ", "राम"),
    ("kannada_folds", "ರಾಮ", "राम"),
    ("devanagari_noop", "विश्वामित्र", "विश्वामित्र"),
    ("latin_noop", "Rama", "Rama"),
    ("slp1_noop", "rAmaH", "rAmaH"),
    ("empty_noop", "", ""),
    # Tamil lacks the voiced/aspirate series: க (KA) has a Devanagari
    # counterpart and folds; unassigned slots are left alone, never mapped to
    # a neighbouring letter.
    ("tamil_ka_folds", "க", "क"),
    ("tamil_unassigned_slot_untouched", "஖", "஖"),
    ("idempotent", normalize_brahmic(MIXED), normalize_brahmic(MIXED)),
]


def test_normalize_brahmic() -> None:
    def check(text, expected):
        assert normalize_brahmic(text) == expected

    check_cases(BRAHMIC_CASES, check)
