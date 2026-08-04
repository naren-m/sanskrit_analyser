"""Dhatupatha index and it-marker stripping.

These tests pin the behaviour as moved from sanskrit_model, plus the
leading-marker fixes from Task 2 (ghu-initial roots, ñi-, and ovit o~).
"""

from sanskrit_analyzer.dhatu.dhatupatha import VOWELS, DhatuKosha, strip_anubandhas


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


def test_ghu_initial_roots_keep_their_own_initial():
    """√ghuṇ 'to turn', √ghuṣ 'to sound': the ghu- is the root, not a marker.

    Eleven roots were being reduced to a single consonant by treating it as
    a cutu it-cluster.
    """
    assert strip_anubandhas("GuRa~") == "GuR"
    assert strip_anubandhas("Guwa~") == "Guw"
    assert strip_anubandhas("Guzi~\\") == "Guz"


def test_strips_leading_nyi_marker():
    """ñiphalā is √phal; ñi- is a recitation marker like ḍu- and ṭu-."""
    assert strip_anubandhas("YiPalA~") == "Pal"


def test_strips_leading_ovit_marker():
    """ohāk is √hā 'to abandon'. Leaving the o~ on caused it to be lost."""
    assert strip_anubandhas("o~hA\\k") == "hA"
    assert strip_anubandhas("o~vijI~\\") == "vij"


def test_strips_stacked_leading_markers():
    """ṭuosphūrjā carries both ṭu- and o~."""
    assert strip_anubandhas("wuo~sPUrjA~") == "sPUrj"


def test_no_root_reduces_to_a_bare_consonant():
    """A single consonant is never a Sanskrit root; single vowels (√i, √ṛ) are.

    Seven roots collapsed this way before the fix, all of the ghu- family.
    The dhatus-full.csv has 30 rows whose dhatu_slp1 is a literal "-"
    placeholder — those are not roots and are excluded.
    """
    kosha = DhatuKosha()
    bad = [
        e for e in kosha.entries
        if e["dhatu_slp1"] != "-"
        and len(e["core_root"]) == 1
        and e["core_root"] not in VOWELS
    ]
    assert bad == [], f"{len(bad)} roots collapsed to a bare consonant"


def test_hā_is_reachable_by_its_clean_root():
    """The whole point: √hā must be findable, or hānam falls to √han."""
    assert DhatuKosha().lookup("hA")
