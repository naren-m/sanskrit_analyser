"""Meter identification: vidyut vṛtta matching + hand-coded anuṣṭubh rules."""
import pytest

vidyut = pytest.importorskip("vidyut")

from sanskrit_analyzer.deep_read.kosha_engine import resolve_data_dir

pytestmark = pytest.mark.skipif(
    resolve_data_dir() is None, reason="vidyut data bundle not installed"
)

from sanskrit_analyzer.prakriya.chandas import anushtubh_form, identify


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
