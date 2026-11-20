"""Golden-set tests for the default chandas engine: real verses, attested meters.

``tests/data/golden_meters.json`` holds 20 attested verses (Ramayana, Gita,
Kalidasa, Bhartrhari, Shankara, stotra literature) plus one ``irregular`` verse
that no classical meter fits. Each verse's L/G truth is cross-checked here by
expanding the canonical Pingala gana definition, so the golden data never
depends on meters-full.csv being correct; a disagreement is a CSV bug.

Everything runs with vidyut absent (``second_opinion=off``) and, where the data
bundle exists, with it present too: vidyut never changes the answer.
"""
import json
from pathlib import Path

import pytest

from sanskrit_analyzer.models.scripts import Script
from sanskrit_analyzer.prakriya import chandas
from sanskrit_analyzer.utils.transliterate import to_slp1
from sanskrit_analyzer.vidyut_data import resolve_data_dir

GOLDEN = json.loads((Path(__file__).resolve().parents[1] / "data" / "golden_meters.json").read_text())
VERSES = GOLDEN["verses"]
IRREGULAR = GOLDEN["irregular"]

#: Pingala's eight trisyllabic ganas + the two single-syllable markers.
GANAS = {
    "ma": "GGG", "na": "LLL", "bha": "GLL", "ya": "LGG",
    "ja": "LGL", "ra": "GLG", "sa": "LLG", "ta": "GGL",
    "ga": "G", "la": "L",
}
_GANA_OF = {v: k for k, v in GANAS.items() if len(v) == 3}
_SLP1_BY_IAST = {r.info.name_iast: r.name for r in chandas._rows()}
_RULE_DEFINED = {"anuṣṭubh": "anuzwuB", "upajāti": "upajAti", "āryā": "AryA"}
_ROWS = {r.name + "|" + r.pattern: r for r in chandas._rows()}


@pytest.fixture(params=["off", "on"])
def second_opinion(request, monkeypatch):
    """Run with vidyut disabled, then (when its data resolves) enabled."""
    if request.param == "off":
        monkeypatch.setattr(chandas, "_classifier", lambda: None)
    elif resolve_data_dir() is None:
        pytest.skip("vidyut data bundle not installed")
    return request.param


def _slp1(text: str) -> str:
    return to_slp1(text, Script.IAST)


def _expected(verse: dict) -> str:
    return _RULE_DEFINED.get(verse["meter"]) or _SLP1_BY_IAST[verse["meter"]]


def _lg_text(scan: str) -> str:
    """IAST text whose syllable weights are ``scan`` ('/' separates pādas)."""
    return "\n".join(" ".join("kā" if w == "G" else "ka" for w in pada) for pada in scan.split("/"))


def _gana_pattern(spec: str) -> str:
    return "".join(GANAS[g] for g in spec.split())


def _decompose(pattern: str) -> str:
    """L/G string -> gana spec: whole trisyllabic ganas, leftovers as la/ga."""
    out = [_GANA_OF[pattern[i:i + 3]] for i in range(0, len(pattern) - len(pattern) % 3, 3)]
    out += ["ga" if ch == "G" else "la" for ch in pattern[len(pattern) - len(pattern) % 3:]]
    return "-".join(out)


#: Plain negative control: broken pāda interiors (``LLLL``) fit no meter, so
#: nothing is identified.
AKHYANIKI_BROKEN_ODD = "GGLGGLLLLGG/LGLGGLLLLGG/GGLGGLLLLGL/LGLGGLLLLGG"

#: 60 syllables whose mātrā totals hit the āryā cuts 12/30/42/57 and then run on
#: to 119: the cut points alone must not name it āryā.
ARYA_CUTS_THEN_RUNS_ON = "G" * 28 + "L" + "G" * 31

FIXED = [v for v in VERSES if v["ganas"]]
ids = lambda cases: [c["id"] for c in cases]  # noqa: E731


# --- the identifier names every golden verse --------------------------------

@pytest.mark.parametrize("verse", VERSES, ids=ids(VERSES))
def test_identifies_every_golden_verse(second_opinion, verse):
    got = chandas.identify(_slp1(verse["text"]))
    assert got.name is not None and got.name.startswith(_expected(verse)), got
    assert len(got.scans) == len(verse["text"].split("\n"))


@pytest.mark.parametrize(
    "verse_id,expected_name,expected_iast",
    [
        ("bg-8.28", "indravajrA", "indravajrā"),       # pāda a ends short: anceps
        ("bg-15.5", "indravajrA", "indravajrā"),       # pure, not upajāti
        ("bg-11.28", "upendravajrA", "upendravajrā"),  # pure, not upajāti
        ("bg-2.22", "upajAti", "upajāti"),             # mixed tristubh
        ("kumarasambhava-1.1", "upajAti", "upajāti"),  # not the ardhasama akhyaniki
        ("ramayana-1.1.1", "anuzwuB (na-vipulA)", "anuṣṭubh"),
        ("raghuvamsha-1.1", "anuzwuB (paTyA)", "anuṣṭubh"),
        ("samkhyakarika-1", "AryA", "āryā"),           # 32 syllables, not śloka
        ("samkhyakarika-2", "AryA", "āryā"),
        ("gangashtakam-1", "malinI", "mālinī"),
        ("shiva-tandava-1", "paYcacAmara", "pañcacāmara"),
    ],
)
def test_specific_rules(second_opinion, verse_id, expected_name, expected_iast):
    verse = next(v for v in VERSES if v["id"] == verse_id)
    got = chandas.identify(_slp1(verse["text"]))
    assert got.name == expected_name
    assert got.info is not None and got.info.name_iast == expected_iast
    assert all(set(s) <= {"L", "G"} for s in got.scans)


@pytest.mark.parametrize(
    "scan,expected",
    [
        # pāda a ends laghu: puṣpitāgrā keeps pāda-final anceps on odd pādas
        ("LLLLLLGLGLGL/LLLLGLLGLGLGG/LLLLLLGLGLGG/LLLLGLLGLGLGG", "puzpitAgrA"),
        ("GGLGGLLGLGG/LGLGGLLGLGG/GGLGGLLGLGG/LGLGGLLGLGG", "AKyAnikI"),
        # ākhyānikī alternation but odd pāda c ends laghu: upajāti, not ākhyānikī
        ("GGLGGLLGLGG/LGLGGLLGLGG/GGLGGLLGLGL/LGLGGLLGLGG", "upajAti"),
    ],
)
def test_ardhasama_odd_pada_anceps_is_narrow(scan, expected):
    padas = scan.split("/")
    assert chandas._scan(padas, "".join(padas)).name == expected


# --- negative controls ------------------------------------------------------

@pytest.mark.parametrize(
    "text",
    [v["text"] for v in IRREGULAR]
    + ["ka ka ka ka ka", "", "   ", "\n\n", "12345", "...", _lg_text(AKHYANIKI_BROKEN_ODD), _lg_text(ARYA_CUTS_THEN_RUNS_ON)],
    ids=[v["id"] for v in IRREGULAR]
    + ["nonsense", "empty", "spaces", "newlines", "digits", "dots", "akhyaniki-broken-odd-pada", "arya-cuts-then-runs-on"],
)
def test_not_verse_is_not_identified(second_opinion, text):
    got = chandas.identify(_slp1(text))
    assert got.name is None and got.info is None


# --- golden data and CSV agree with Pingala --------------------------------

@pytest.mark.parametrize("verse", FIXED, ids=ids(FIXED))
def test_golden_padas_match_canonical_ganas(verse):
    canon = _gana_pattern(verse["ganas"])
    assert len(canon) == verse["syllables"]
    for pada in verse["text"].split("\n"):
        weights = chandas.syllable_weights(_slp1(pada))
        assert chandas._matches(weights, canon), f"{weights} != {canon}"


@pytest.mark.parametrize("verse", FIXED, ids=ids(FIXED))
def test_csv_row_matches_canonical_ganas(verse):
    rows = [r for r in chandas._rows() if r.info.name_iast == verse["meter"]]
    assert [r.padas for r in rows] == [(_gana_pattern(verse["ganas"]),)]


@pytest.mark.parametrize("row", list(_ROWS.values()), ids=list(_ROWS))
def test_csv_row_is_self_consistent(row):
    """ganas cell expands to the pattern, spelled canonically; syllables column
    equals the total; patterns contain only L and G."""
    gana_padas = row.info.ganas.split("/")
    assert len(gana_padas) == len(row.padas)
    for spec, pattern in zip(gana_padas, row.padas, strict=True):
        assert "".join(GANAS[g] for g in spec.split("-") if g) == pattern
        assert spec == _decompose(pattern)
        assert set(pattern) <= {"L", "G"}
    assert row.info.syllables == sum(len(p) for p in row.padas)


def test_newlines_survive_transliteration():
    """A verse typed one pāda per line keeps its line breaks through to_slp1."""
    for text, script in (("rāmāya\nrāmabhadrāya", Script.IAST), ("रामाय\nरामभद्राय", Script.DEVANAGARI)):
        assert to_slp1(text, script).count("\n") == 1
