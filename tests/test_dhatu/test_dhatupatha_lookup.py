"""Dhātupāṭha lookup: script handling, citation spellings, and conjugation."""

import pytest

from sanskrit_analyzer.dhatu import conjugation
from sanskrit_analyzer.dhatu.dhatupatha import (
    entry_to_dict,
    get_dhatu_kosha,
    undo_citation_spelling,
)

needs_vidyut = pytest.mark.skipif(
    not conjugation.is_available(), reason="vidyut data bundle not available"
)


@pytest.fixture(scope="module")
def kosha():
    return get_dhatu_kosha()


class TestFind:
    """Root lookup across scripts and Dhātupāṭha citation spellings."""

    @pytest.mark.parametrize(
        "query,expected_code",
        [
            ("gam", "01.1137"),
            ("गम्", "01.1137"),
            ("BU", "01.0001"),
            ("bhū", "01.0001"),
            ("भू", "01.0001"),
        ],
    )
    def test_same_root_in_any_script(self, kosha, query, expected_code) -> None:
        assert expected_code in {e["code"] for e in kosha.find(query)}

    @pytest.mark.parametrize(
        "query,root",
        [
            ("nah", "Rah"),  # 6.1.65: the index cites ṇah
            ("naś", "naS"),
            ("sthā", "sTA"),  # 6.1.64 + ṣṭutva: the index cites ṣṭhā
            ("sad", "sad"),
        ],
    )
    def test_citation_spelling_is_undone(self, kosha, query, root) -> None:
        hits = kosha.find(query)
        assert hits and all(e["core_root"] == root for e in hits)

    def test_citation_form_resolves_to_root(self, kosha) -> None:
        """ḍukṛñ is the Dhātupāṭha's citation of √kṛ."""
        assert {e["core_root"] for e in kosha.find("ḍukṛñ")} == {"kf"}

    def test_homonymous_roots_all_returned(self, kosha) -> None:
        """√kṛ is listed in both the 5th and 8th gaṇa."""
        assert {e["gana"] for e in kosha.find("kṛ")} == {"5", "8"}

    def test_unknown_root(self, kosha) -> None:
        assert kosha.find("xyznotaroot") == []

    def test_empty_query(self, kosha) -> None:
        assert kosha.find("") == []


class TestSearch:
    """Substring search over roots and artha."""

    def test_search_by_artha(self, kosha) -> None:
        results = kosha.search("gatau", limit=5)
        assert results and all("gatau" in e["artha_iast"] for e in results)

    def test_search_respects_limit(self, kosha) -> None:
        assert len(kosha.search("a", limit=7)) == 7

    def test_exact_root_match_comes_first(self, kosha) -> None:
        assert kosha.search("gam", limit=5)[0]["code"] == "01.1137"

    def test_slp1_case_is_significant(self, kosha) -> None:
        """BU is √bhū; matching it must not fold case into bu."""
        assert any(e["core_root"] == "BU" for e in kosha.search("BU", limit=5))


class TestStats:
    """Whole-Dhātupāṭha counts."""

    def test_count_and_gana_stats_agree(self, kosha) -> None:
        stats = kosha.gana_stats()
        assert kosha.count() > 2000
        assert sorted(stats) == list(range(1, 11))
        assert sum(stats.values()) == kosha.count()


class TestEntryToDict:
    """The shape the API and MCP tools both serve."""

    @pytest.mark.parametrize(
        "cited,living",
        [
            ("Rah", "nah"),  # 6.1.65 ṇo naḥ
            ("Rakz", "nakz"),
            ("zWA", "sTA"),  # 6.1.64 + ṣṭutva undone through the cluster
            ("zRA", "snA"),
            ("gam", "gam"),  # untouched
        ],
    )
    def test_citation_spelling_is_undone_for_display(self, cited, living) -> None:
        assert undo_citation_spelling(cited) == living

    def test_presented_root_is_the_living_root(self, kosha) -> None:
        """√nah is cited as ṇah; reporting √ṇah would name a root that does not exist."""
        entry = entry_to_dict(kosha.find("nah")[0])
        assert entry["root_slp1"] == "nah"
        assert entry["root_devanagari"] == "नह्"
        assert entry["upadesha_devanagari"].startswith("ण")

    def test_entry_fields(self, kosha) -> None:
        entry = entry_to_dict(kosha.find("gam")[0])
        assert entry["code"] == "01.1137"
        assert entry["root_slp1"] == "gam"
        assert entry["root_devanagari"] == "गम्"
        assert entry["upadesha_slp1"] == "ga\\mx~"
        assert entry["gana"] == 1
        assert entry["gana_name"] == "bhvādi"
        assert entry["artha_iast"] == "gatau"
        assert entry["curated"] is True


@needs_vidyut
class TestConjugation:
    """Forms are derived by vidyut, not read from a table."""

    def test_lat_paradigm(self) -> None:
        rows = conjugation.conjugate("01.1137", "lat")
        forms = {(r["purusha"], r["vacana"]): r["forms_iast"] for r in rows}
        assert forms[("prathama", "eka")] == ["gacchati"]
        assert forms[("madhyama", "dvi")] == ["gacchathaḥ"]
        assert forms[("uttama", "bahu")] == ["gacchāmaḥ"]

    def test_pada_is_derived_not_assumed(self) -> None:
        """√gam is parasmaipada only; √nah forms both."""
        assert conjugation.padas_for("01.1137") == ["parasmaipada"]
        assert conjugation.padas_for("04.0062") == ["parasmaipada", "ātmanepada"]

    def test_every_lakara_derives(self) -> None:
        for lakara in conjugation.LAKARA_NAMES:
            assert conjugation.conjugate("01.1137", lakara), lakara

    def test_lin_is_read_as_vidhi_lin(self) -> None:
        assert conjugation.normalize_lakara("lin") == "vidhilin"

    def test_unknown_lakara_rejected(self) -> None:
        assert conjugation.normalize_lakara("nope") is None
        with pytest.raises(KeyError):
            conjugation.conjugate("01.1137", "nope")

    def test_unknown_code_rejected(self) -> None:
        with pytest.raises(KeyError):
            conjugation.conjugate("99.9999", "lat")
