"""Dhatupatha index, it-marker stripping, and root lookup.

Stripping pins the behaviour as moved from sanskrit_model, plus the
leading-marker fixes from Task 2 (ghu-initial roots, ñi-, and ovit o~).
"""

import pytest

from sanskrit_analyzer.dhatu.dhatupatha import (
    VOWELS,
    DhatuKosha,
    entry_to_dict,
    get_dhatu_kosha,
    strip_anubandhas,
    undo_citation_spelling,
)
from tests._cases import check_cases


@pytest.fixture(scope="module")
def kosha():
    return get_dhatu_kosha()


STRIP_CASES = [
    ("accent-marks", "yu\\ja~", "yuj"),
    # ḍukṛñ is √kṛ — the ḍu- is a recitation-list marker.
    ("leading-du-marker", "qukf\\Y", "kf"),
    ("trailing-nasal-marker-and-its-vowel", "Bava~", "Bav"),
    # √ghuṇ 'to turn', √ghuṣ 'to sound': the ghu- is the root, not a marker.
    # Eleven roots were being reduced to a single consonant by treating it as
    # a cutu it-cluster.
    ("ghu-initial-keeps-initial-ghuR", "GuRa~", "GuR"),
    ("ghu-initial-keeps-initial-Guw", "Guwa~", "Guw"),
    ("ghu-initial-keeps-initial-Guz", "Guzi~\\", "Guz"),
    # ñiphalā is √phal; ñi- is a recitation marker like ḍu- and ṭu-.
    ("leading-nyi-marker", "YiPalA~", "Pal"),
    # ohāk is √hā 'to abandon'. Leaving the o~ on caused it to be lost.
    ("leading-ovit-marker-hA", "o~hA\\k", "hA"),
    ("leading-ovit-marker-vij", "o~vijI~\\", "vij"),
    # ṭuosphūrjā carries both ṭu- and o~.
    ("stacked-leading-markers", "wuo~sPUrjA~", "sPUrj"),
]


def test_strip_anubandhas():
    def check(upadesha, root):
        assert strip_anubandhas(upadesha) == root

    check_cases(STRIP_CASES, check)


def test_kosha_loads_every_row():
    kosha = DhatuKosha()
    assert len(kosha.entries) == 2259
    curated = [e for e in kosha.entries if e["curated"]]
    assert len(curated) > 0
    assert all(e["core_root"] for e in curated)


def test_by_gana_filters(kosha):
    first_gana = kosha.by_gana(1)
    assert first_gana
    assert all(int(e["gana"]) == 1 for e in first_gana)


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


def test_lookup_by_clean_root():
    kosha = DhatuKosha()
    assert kosha.lookup("gam")
    # The whole point: √hā must be findable, or hānam falls to √han.
    assert kosha.lookup("hA")


FIND_CODE_CASES = [
    ("slp1-gam", "gam", "01.1137"),
    ("devanagari-gam", "गम्", "01.1137"),
    ("slp1-bhu", "BU", "01.0001"),
    ("iast-bhu", "bhū", "01.0001"),
    ("devanagari-bhu", "भू", "01.0001"),
]

FIND_ROOTS_CASES = [
    ("citation-nah-6.1.65-index-cites-Rah", "nah", {"Rah"}),
    ("citation-naS", "naś", {"naS"}),
    ("citation-sthA-6.1.64-sTutva-index-cites-zWA", "sthā", {"sTA"}),
    ("citation-sad", "sad", {"sad"}),
    # ḍukṛñ is the Dhātupāṭha's citation of √kṛ.
    ("citation-form-dukfY-resolves-to-kf", "ḍukṛñ", {"kf"}),
]


def test_find(kosha):
    """Root lookup across scripts and Dhātupāṭha citation spellings."""

    def check_code(query, code):
        assert code in {e["code"] for e in kosha.find(query)}

    def check_roots(query, roots):
        hits = kosha.find(query)
        assert hits and {e["core_root"] for e in hits} == roots

    check_cases(FIND_CODE_CASES, check_code)
    check_cases(FIND_ROOTS_CASES, check_roots)
    # √kṛ is listed in both the 5th and 8th gaṇa.
    assert {e["gana"] for e in kosha.find("kṛ")} == {"5", "8"}
    assert kosha.find("xyznotaroot") == []
    assert kosha.find("") == []


def test_search(kosha):
    """Substring search over roots and artha."""
    results = kosha.search("gatau", limit=5)
    assert results and all("gatau" in e["artha_iast"] for e in results)
    assert len(kosha.search("a", limit=7)) == 7
    assert kosha.search("gam", limit=5)[0]["code"] == "01.1137"
    # BU is √bhū; matching it must not fold case into bu.
    assert any(e["core_root"] == "BU" for e in kosha.search("BU", limit=5))


def test_count_and_gana_stats_agree(kosha):
    stats = kosha.gana_stats()
    assert kosha.count() > 2000
    assert sorted(stats) == list(range(1, 11))
    assert sum(stats.values()) == kosha.count()


UNDO_CITATION_CASES = [
    ("6.1.65-No-naH-Rah", "Rah", "nah"),
    ("6.1.65-Rakz", "Rakz", "nakz"),
    ("6.1.64-sTutva-undone-through-cluster-zWA", "zWA", "sTA"),
    ("6.1.64-zRA", "zRA", "snA"),
    ("untouched-gam", "gam", "gam"),
]


def test_entry_to_dict(kosha):
    """The shape the API and MCP tools both serve."""

    def check(cited, living):
        assert undo_citation_spelling(cited) == living

    check_cases(UNDO_CITATION_CASES, check)

    # √nah is cited as ṇah; reporting √ṇah would name a root that does not exist.
    entry = entry_to_dict(kosha.find("nah")[0])
    assert entry["root_slp1"] == "nah"
    assert entry["root_devanagari"] == "नह्"
    assert entry["upadesha_devanagari"].startswith("ण")

    entry = entry_to_dict(kosha.find("gam")[0])
    assert entry["code"] == "01.1137"
    assert entry["root_slp1"] == "gam"
    assert entry["root_devanagari"] == "गम्"
    assert entry["upadesha_slp1"] == "ga\\mx~"
    assert entry["gana"] == 1
    assert entry["gana_name"] == "bhvādi"
    assert entry["artha_iast"] == "gatau"
    assert entry["curated"] is True
