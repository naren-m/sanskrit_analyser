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
from tests._cases import check_cases

MANDAKRANTA = "kaScitkAntAvirahaguruRA svADikArapramattaH"  # Meghadūta 1.1
BG_2_47 = ("karmaRyevADikAraste mA Palezu kadAcana . "
           "mA karmaPalaheturBUrmA te saNgo 'stvakarmaRi")


def _is(expected):
    return lambda name: name == expected


def _contains(fragment):
    return lambda name: name is not None and fragment in name


# (id, SLP1 text, predicate on identify(text).name)
IDENTIFY_CASES = [
    ("mandakranta-vrtta-matched", MANDAKRANTA, _is("mandAkrAntA")),
    # vidyut's chandas indexes a 256-entry table by codepoint, so a stray em
    # dash or ZWJ left in the SLP1 used to panic (a BaseException) mid-verse.
    ("em-dash-and-zwj-do-not-panic",
     "kaScitkAntAvirahaguruRA \u2014 svADikAra\u200dpramattaH", _is("mandAkrAntA")),
    # BG 2.47: vidyut returns no vṛtta; our anuṣṭubh rule fires.
    ("bg-2.47-anushtubh-pathya-fallback", BG_2_47, _contains("anuzwuB")),
    ("prose-has-no-meter", "rAmaH gacCati", _is(None)),
    # Rāmāyaṇa 3.10.3, a plain pathyā śloka. vidyut's classifier fuzzy-matches
    # 32-syllable lines to the jāti meter upagīti; 1,005 corpus ślokas hit this.
    ("valid-sloka-beats-vidyut-jati-fuzzy-match",
     "kintu vakzyAmyahaM devi tvayEvoktamidaM vacaH . "
     "kzatriyErDAryate cApo nArtaSabdo Bavediti", _is("anuzwuB (paTyA)")),
]


def test_identify_names_the_meter():
    def check(text, ok):
        name = identify(text).name
        assert ok(name), f"got {name!r}"

    check_cases(IDENTIFY_CASES, check)


# pathyā: 8 syll/pāda, 5th L, 6th G, 7th G in odd pādas / L in even pādas.
PATHYA, EVEN = "GGGGLGGG", "GGGGLGLG"


def _odd(syll_5_7: str) -> str:
    return "GGGG" + syll_5_7 + "G"


# (id, four pāda scans, expected anushtubh_form)
ANUSHTUBH_CASES = [
    ("pathya", [PATHYA, EVEN, PATHYA, EVEN], "paTyA"),
    ("not-8-syllable-is-none", ["GGGG", "GG", "G", "G"], None),
    ("odd-LGG-pathya", [_odd("LGG"), EVEN, _odd("LGG"), EVEN], "paTyA"),
    ("odd-LLL-na-vipula", [_odd("LLL"), EVEN, _odd("LLL"), EVEN], "na-vipulA"),
    ("odd-GLL-bha-vipula", [_odd("GLL"), EVEN, _odd("GLL"), EVEN], "Ba-vipulA"),
    ("odd-GGG-ma-vipula", [_odd("GGG"), EVEN, _odd("GGG"), EVEN], "ma-vipulA"),
    ("odd-GLG-ra-vipula", [_odd("GLG"), EVEN, _odd("GLG"), EVEN], "ra-vipulA"),
    # ja-gaṇa is the even-pāda shape; not a śloka odd pāda
    ("odd-LGL-ja-gana-is-none", [_odd("LGL"), EVEN, _odd("LGL"), EVEN], None),
    ("odd-LLG-sa-gana-no-vipula", [_odd("LLG"), EVEN, _odd("LLG"), EVEN], None),
    ("mixed-odd-padas-report-the-vipula", [PATHYA, EVEN, "GGGGLLLG", EVEN], "na-vipulA"),
    ("even-pada-must-be-ja-gana", [PATHYA, "GGGGLGGG", PATHYA, EVEN], None),
]


def test_anushtubh_form():
    def check(padas, expected):
        assert anushtubh_form(padas) == expected

    check_cases(ANUSHTUBH_CASES, check)


def test_vrtta_carries_display_info():
    """A matched vṛtta gains IAST/Devanāgarī names and its gaṇa breakdown."""
    r = identify(MANDAKRANTA)
    assert r.scans and all(ch in "GL" for ch in r.scans[0])
    assert r.info is not None
    assert r.info.name_iast == "mandākrāntā"
    assert r.info.name_deva == "मन्दाक्रान्ता"
    assert r.info.syllables == 17
    assert r.info.ganas == "ma-bha-na-ta-ta-ga-ga"
    assert r.info.yati == (4, 6)


def test_anushtubh_carries_display_info():
    """The śloka has no meters-full.csv row, so its display forms are constants."""
    r = identify(BG_2_47)
    assert r.info is not None
    assert r.info.name_iast == "anuṣṭubh"
    assert r.info.syllables == 32
    # The pathyā/vipulā form stays in .name, not in .info.
    assert "anuzwuB" in r.name


def test_unmatched_verse_has_no_info():
    r = identify("a")
    assert r.name is None
    assert r.info is None


# (id, name, scan, expected syllables or None for no match)
METER_INFO_CASES = [
    # vidyut ships two meters named SrI; the scan picks the right one.
    ("homonym-SrI-1-syllable-by-scan", "SrI", ["G"], 1),
    ("homonym-SrI-11-syllable-by-scan", "SrI", ["GLLGG", "LLLLGG"], 11),
    # Without a scan we cannot choose, so the first entry is returned.
    ("homonym-no-scan-returns-first", "SrI", None, 1),
    ("unknown-name-is-none", "notameter", None, None),
]


def test_meter_info_lookup():
    def check(name, scan, syllables):
        info = meter_info(name, scan) if scan else meter_info(name)
        got = info.syllables if info else None
        assert got == syllables

    check_cases(METER_INFO_CASES, check)


def test_every_meter_row_loads():
    """The whole CSV parses into MeterInfo, including the ';'-joined yati field."""
    infos = [info for entries in _meter_table().values() for _, info in entries]
    assert len(infos) == 145
    assert all(isinstance(i.yati, tuple) for i in infos)
    assert all(isinstance(y, int) for i in infos for y in i.yati)
