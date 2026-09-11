"""Meter identification: vidyut vṛtta matching + hand-coded anuṣṭubh rules."""
import pytest

vidyut = pytest.importorskip("vidyut")

from sanskrit_analyzer.deep_read.kosha_engine import resolve_data_dir

pytestmark = pytest.mark.skipif(
    resolve_data_dir() is None, reason="vidyut data bundle not installed"
)

from sanskrit_analyzer.prakriya.chandas import (
    _meter_table,
    anushtubh_form,
    identify,
    meter_info,
)


def test_mandakranta_identified():
    # Meghadūta 1.1 first pāda pair
    r = identify("kaScitkAntAvirahaguruRA svADikArapramattaH")
    assert r.name == "mandAkrAntA"
    assert r.scans and all(ch in "GL" for ch in r.scans[0])


def test_anushtubh_pathya_fallback():
    # BG 2.47: karmaṇy evādhikāras te... vidyut returns no vṛtta; our rule fires.
    r = identify("karmaRyevADikAraste mA Palezu kadAcana . "
                 "mA karmaPalaheturBUrmA te saNgo 'stvakarmaRi")
    assert r.name is not None and "anuzwuB" in r.name


def test_anushtubh_form_pure_function():
    # pathyā: 8 syll/pāda, 5th L, 6th G, 7th G in odd pādas / L in even pādas
    odd, even = "GGGGLGGG", "GGGGLGLG"
    assert anushtubh_form([odd, even, odd, even]) == "paTyA"
    assert anushtubh_form(["GGGG", "GG", "G", "G"]) is None  # not 8-syllable


def test_prose_returns_none_name():
    r = identify("rAmaH gacCati")
    assert r.name is None


@pytest.mark.parametrize(
    "odd_5_7,expected",
    [
        ("LGG", "paTyA"),
        ("LLL", "na-vipulA"),
        ("GLL", "Ba-vipulA"),
        ("GGG", "ma-vipulA"),
        ("GLG", "ra-vipulA"),
        ("LGL", None),  # ja-gaṇa is the even-pāda shape; not a śloka odd pāda
        ("LLG", None),  # sa-gaṇa: no such vipulā
    ],
)
def test_anushtubh_odd_pada_forms(odd_5_7, expected):
    odd = "GGGG" + odd_5_7 + "G"
    even = "GGGGLGLG"
    assert anushtubh_form([odd, even, odd, even]) == expected


def test_anushtubh_mixed_odd_padas_reports_the_vipula():
    pathya = "GGGGLGGG"
    na_vipula = "GGGGLLLG"
    even = "GGGGLGLG"
    assert anushtubh_form([pathya, even, na_vipula, even]) == "na-vipulA"


def test_anushtubh_even_pada_must_be_ja_gana():
    odd = "GGGGLGGG"
    assert anushtubh_form([odd, "GGGGLGGG", odd, "GGGGLGLG"]) is None


def test_vrtta_carries_display_info():
    """A matched vṛtta gains IAST/Devanāgarī names and its gaṇa breakdown."""
    r = identify("kaScitkAntAvirahaguruRA svADikArapramattaH")
    assert r.info is not None
    assert r.info.name_iast == "mandākrāntā"
    assert r.info.name_deva == "मन्दाक्रान्ता"
    assert r.info.syllables == 17
    assert r.info.ganas == "ma-bha-na-ta-ta-ga-ga"
    assert r.info.yati == (4, 6)


def test_anushtubh_carries_display_info():
    """The śloka has no meters-full.csv row, so its display forms are constants."""
    r = identify("karmaRyevADikAraste mA Palezu kadAcana . "
                 "mA karmaPalaheturBUrmA te saNgo 'stvakarmaRi")
    assert r.info is not None
    assert r.info.name_iast == "anuṣṭubh"
    assert r.info.syllables == 32
    # The pathyā/vipulā form stays in .name, not in .info.
    assert "anuzwuB" in r.name


def test_unmatched_verse_has_no_info():
    r = identify("a")
    assert r.name is None
    assert r.info is None


def test_homonymous_meters_disambiguate_by_scan():
    """vidyut ships two meters named SrI; the scan picks the right one."""
    assert meter_info("SrI", ["G"]).syllables == 1
    assert meter_info("SrI", ["GLLGG", "LLLLGG"]).syllables == 11
    # Without a scan we cannot choose, so the first entry is returned.
    assert meter_info("SrI").syllables == 1


def test_meter_info_unknown_name():
    assert meter_info("notameter") is None


def test_every_meter_row_loads():
    """The whole CSV parses into MeterInfo, including the ';'-joined yati field."""
    infos = [info for entries in _meter_table().values() for _, info in entries]
    assert len(infos) == 145
    assert all(isinstance(i.yati, tuple) for i in infos)
    assert all(isinstance(y, int) for i in infos for y in i.yati)


def test_valid_sloka_beats_vidyut_jati_fuzzy_match():
    # Rāmāyaṇa 3.10.3, a plain pathyā śloka. vidyut's classifier fuzzy-matches
    # 32-syllable lines to the jāti meter upagīti; 1,005 corpus ślokas hit this.
    r = identify("kintu vakzyAmyahaM devi tvayEvoktamidaM vacaH . "
                 "kzatriyErDAryate cApo nArtaSabdo Bavediti")
    assert r.name == "anuzwuB (paTyA)"
