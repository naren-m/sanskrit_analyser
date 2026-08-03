"""Dhatupatha index and it-marker stripping.

These tests pin the behaviour as moved from sanskrit_model, including two
known-wrong cases (see test_known_defects_pinned) that Task 2 fixes.
"""

from sanskrit_analyzer.dhatu.dhatupatha import DhatuKosha, strip_anubandhas


def test_strips_accent_marks():
    assert strip_anubandhas("yu\\ja~") == "yuj"


def test_strips_leading_du_marker():
    """ḍukṛñ is √kṛ — the ḍu- is a recitation-list marker."""
    assert strip_anubandhas("qukf\\Y") == "kf"


def test_strips_trailing_nasal_marker_and_its_vowel():
    assert strip_anubandhas("Bava~") == "Bav"


def test_kosha_loads_every_row():
    kosha = DhatuKosha()
    assert len(kosha.entries) == 2259


def test_kosha_prefers_curated_core_root():
    kosha = DhatuKosha()
    curated = [e for e in kosha.entries if e["curated"]]
    assert len(curated) > 0
    assert all(e["core_root"] for e in curated)


def test_lookup_finds_a_common_root():
    kosha = DhatuKosha()
    assert kosha.lookup("gam")


def test_by_gana_filters():
    kosha = DhatuKosha()
    first_gana = kosha.by_gana(1)
    assert first_gana
    assert all(int(e["gana"]) == 1 for e in first_gana)


def test_known_defects_pinned():
    """Behaviour that is WRONG but is being moved unchanged; Task 2 fixes it.

    √ghuṇ loses its own initial ghu- (read as a marker), and the ovit marker
    o~ of √hā is not recognised as leading at all.
    """
    assert strip_anubandhas("GuRa~") == "R"
    assert strip_anubandhas("o~hA\\k") == "o~hA"
    assert strip_anubandhas("YiPalA~") == "YiPal"
