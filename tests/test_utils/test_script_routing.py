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


def test_to_devanagari_transliterates_slp1():
    assert to_devanagari("rAmaH") == "रामः"


def test_to_devanagari_passes_through_existing_devanagari():
    assert to_devanagari("रामः") == "रामः"


def test_to_devanagari_empty_is_noop():
    assert to_devanagari("") == ""


def test_to_iast_from_devanagari():
    assert to_iast("रामः") == "rāmaḥ"


def test_to_iast_passes_through_latin():
    # Plain-Latin / already-IAST spelling is returned unchanged.
    assert to_iast("Rama") == "Rama"


def test_to_iast_empty_is_noop():
    assert to_iast("") == ""


def test_is_devanagari_detects_script():
    assert is_devanagari("राम")
    assert not is_devanagari("Rama")
    assert not is_devanagari("rAmaH")  # SLP1 is Latin-range
    assert not is_devanagari("")


# --------------------------------------------------------------------------
# normalize_brahmic — sibling-script folding
# --------------------------------------------------------------------------


def test_normalize_brahmic_folds_gujarati_to_devanagari():
    # વ (U+0AB5) and ા (U+0ABE) sit at the same block offsets as व / ा.
    assert normalize_brahmic("વા") == "वा"


def test_normalize_brahmic_folds_a_mixed_script_name():
    """An LLM-emitted name with Gujarati characters spliced into Devanagari.

    ``विश્વामित्र`` is how one Viśvāmitra duplicate reached the Ramayanam KG
    (ramayanam#419) — visually identical, but two of its characters come from
    the Gujarati block, so every downstream key differs.
    """
    assert normalize_brahmic("विश્વामित्र") == "विश्वामित्र"


def test_normalize_brahmic_folds_other_sibling_blocks():
    assert normalize_brahmic("রাম") == "राम"  # Bengali
    assert normalize_brahmic("రామ") == "राम"  # Telugu
    assert normalize_brahmic("ರಾಮ") == "राम"  # Kannada


def test_normalize_brahmic_is_noop_for_devanagari_and_latin():
    assert normalize_brahmic("विश्वामित्र") == "विश्वामित्र"
    assert normalize_brahmic("Rama") == "Rama"
    assert normalize_brahmic("rAmaH") == "rAmaH"
    assert normalize_brahmic("") == ""


def test_normalize_brahmic_leaves_unassigned_slots_alone():
    """Tamil lacks the voiced/aspirate series; those slots must not be invented.

    ``க`` (Tamil KA) has a Devanagari counterpart and folds; the Tamil block's
    unassigned offsets have none and are left untouched rather than mapped to a
    neighbouring letter.
    """
    assert normalize_brahmic("க") == "क"
    assert normalize_brahmic("஖") == "஖"  # unassigned Tamil slot


def test_normalize_brahmic_is_idempotent():
    once = normalize_brahmic("विश્વामित्र")
    assert normalize_brahmic(once) == once
