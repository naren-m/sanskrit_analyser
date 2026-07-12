"""Tests for auto-detecting script routing (issue #393).

Lifted from the Ramayanam knowledge-graph reader (``text_hygiene``) so the
auto-detecting transliteration is shared across scripture apps. These pin the
same behaviour the Ramayanam tests asserted, proving the lift is faithful.
"""
from __future__ import annotations

from sanskrit_analyzer.utils.script_routing import (
    is_devanagari,
    to_devanagari,
    to_iast,
)


def test_to_devanagari_transliterates_slp1():
    assert to_devanagari("rAmaH") == "रामः"


def test_to_devanagari_passes_through_existing_devanagari():
    assert to_devanagari("रामः") == "रामः"


def test_to_devanagari_empty_is_noop():
    assert to_devanagari("") == ""


def test_to_devanagari_transliterates_iast():
    # IAST input must be detected as IAST, not blindly treated as SLP1.
    # The old code fed IAST to an SLP1->Deva transliteration and mangled the
    # visarga: "yogaḥ" -> "योगḥ" instead of "योगः".
    assert to_devanagari("yogaḥ") == "योगः"


def test_to_iast_from_devanagari():
    assert to_iast("रामः") == "rāmaḥ"


def test_to_iast_passes_through_latin():
    # Plain-Latin / already-IAST spelling is returned unchanged.
    assert to_iast("Rama") == "Rama"


def test_to_iast_decodes_slp1():
    # SLP1 is Latin-range, so the old is_devanagari() check let it pass through
    # undecoded: "yogaH" stayed "yogaH" instead of becoming "yogaḥ".
    assert to_iast("yogaH") == "yogaḥ"


def test_to_iast_empty_is_noop():
    assert to_iast("") == ""


def test_is_devanagari_detects_script():
    assert is_devanagari("राम")
    assert not is_devanagari("Rama")
    assert not is_devanagari("rAmaH")  # SLP1 is Latin-range
    assert not is_devanagari("")
