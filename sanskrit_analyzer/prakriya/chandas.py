"""Chandas (meter) identification.

``vidyut.chandas`` handles fixed-template vṛttas via meters.tsv. The śloka
(anuṣṭubh) is NOT a fixed L/G template, so when vidyut finds no match we apply
the classical pathyā/vipulā checks ourselves (design doc §3.3.5):

* every pāda has 8 syllables;
* syllables 2–3 are never both laghu;
* even pādas take ja-gaṇa (L G L) at syllables 5–7 (pāda-final syllable is anceps);
* odd pādas take ya-gaṇa (L G G) -> pathyā, or one of the four vipulā gaṇas
  na (LLL), bha (GLL), ma (GGG), ra (GLG). Anything else is not a śloka.
"""
from __future__ import annotations

import csv
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from sanskrit_analyzer.vidyut_data import VidyutUnavailable, resolve_data_dir

_METERS_CSV = Path(__file__).resolve().parents[1] / "data" / "meters-full.csv"


@dataclass(frozen=True)
class MeterInfo:
    """Display and structural detail for an identified meter.

    vidyut's meters.tsv carries only name, class and L/G pattern, so the SLP1
    name is all ``identify`` could report. These come from data/meters-full.csv.
    """

    name_iast: str
    name_deva: str
    syllables: int | None
    ganas: str                # e.g. "ta-bha-ja-ja-ga-ga"
    yati: tuple[int, ...]     # caesura positions; empty when unrecorded


@dataclass(frozen=True)
class ChandasResult:
    name: str | None        # e.g. "mandAkrAntA", "anuzwuB (paTyA)"
    scans: list[str]        # per-pāda weight strings, e.g. "GGLG..."
    notes: str | None = None
    info: MeterInfo | None = None


@lru_cache(maxsize=1)
def _meter_table() -> dict[str, list[tuple[str, MeterInfo]]]:
    """``name_slp1 -> [(pattern, info)]`` from data/meters-full.csv.

    The value is a list, not a single entry, because vidyut ships two distinct
    meters both named ``SrI`` - a 1-syllable one and an 11-syllable one. Keying
    by name alone would silently drop whichever came second.
    """
    table: dict[str, list[tuple[str, MeterInfo]]] = {}
    with _METERS_CSV.open(encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            info = MeterInfo(
                name_iast=row["name_iast"],
                name_deva=row["name_deva"],
                syllables=int(row["syllables"]) if row["syllables"] else None,
                ganas=row["ganas"],
                yati=tuple(int(p) for p in row["yati_positions"].split(";") if p.strip()),
            )
            table.setdefault(row["name_slp1"], []).append((row["pattern"], info))
    return table


def meter_info(name_slp1: str, scans: list[str] | None = None) -> MeterInfo | None:
    """Look up display detail for a meter, disambiguating homonyms by scan.

    ``SrI`` names two meters, so when a scan is available the CSV pattern (with
    its ``|`` yati separators stripped) picks the row. With no scan, or none
    matching, the first row is the only sensible answer.
    """
    entries = _meter_table().get(name_slp1)
    if not entries:
        return None
    if scans:
        observed = "".join(scans)
        for pattern, info in entries:
            if pattern.replace("|", "") == observed:
                return info
    return entries[0][1]


# The śloka is not a fixed L/G template, so it has no row in the vṛtta-only
# meters-full.csv and its display forms are supplied here. The identified
# pathyā/vipulā form stays in ``ChandasResult.name``.
_ANUSTUBH_INFO = MeterInfo(
    name_iast="anuṣṭubh",
    name_deva="अनुष्टुभ्",
    syllables=32,
    ganas="",
    yati=(),
)


@lru_cache(maxsize=1)
def _classifier():
    data_dir = resolve_data_dir()
    if data_dir is None:
        raise VidyutUnavailable("vidyut data bundle not found; chandas unavailable.")
    from vidyut.chandas import Chandas

    return Chandas(str(data_dir / "chandas" / "meters.tsv"))


def identify(slp1_verse: str) -> ChandasResult:
    match = _classifier().classify(slp1_verse.replace(".", " "))
    scans = ["".join(str(a.weight) for a in row) for row in (match.aksharas or [])]
    # vidyut fuzzy-matches even tiny fragments (5 syllables of prose match a
    # short vṛtta); below one pāda's worth of syllables a "meter" is noise.
    if sum(len(s) for s in scans) < 8:
        return ChandasResult(name=None, scans=scans, notes="too short for meter")

    # A vidyut name that meters-full.csv also carries is a vṛtta: an exact L/G
    # template match, and the strongest answer we can give.
    name = str(match.padya) if match.padya is not None else None
    info = meter_info(name, scans) if name else None
    if info is not None:
        return ChandasResult(name=name, scans=scans, info=info)

    # Any name left is a fuzzy jāti (mātrā) match such as upagIti, which our
    # table does not carry. A valid śloka scan outranks it; śloka itself has no
    # fixed template for vidyut to match, so only our own rules can find it.
    form = anushtubh_form(_as_four_padas(scans))
    if form:
        return ChandasResult(name=f"anuzwuB ({form})", scans=scans, info=_ANUSTUBH_INFO)
    if name:
        return ChandasResult(name=name, scans=scans)
    return ChandasResult(name=None, scans=scans, notes="no meter matched (prose or corrupt text?)")


def _as_four_padas(scans: list[str]) -> list[str]:
    """vidyut may scan a śloka as one row of 32 or 2×16; split to 4×8 pādas."""
    if len(scans) == 1 and len(scans[0]) == 32:
        s = scans[0]
        return [s[0:8], s[8:16], s[16:24], s[24:32]]
    if len(scans) == 2 and all(len(s) == 16 for s in scans):
        return [scans[0][:8], scans[0][8:], scans[1][:8], scans[1][8:]]
    return scans


# Odd-pāda syllables 5–7 of a classical śloka. pathyā takes ya-gaṇa; the four
# vipulā forms take na, bha, ma, ra. ja-gaṇa (LGL) in an odd pāda is the even-pāda
# shape and is not a śloka form at all.
_ODD_PADA_FORMS = {
    "LGG": "paTyA",
    "LLL": "na-vipulA",
    "GLL": "Ba-vipulA",
    "GGG": "ma-vipulA",
    "GLG": "ra-vipulA",
}


def anushtubh_form(scans: list[str]) -> str | None:
    """Return the śloka form ("paTyA" or "<gaṇa>-vipulA") for 4 pāda scans, else None.

    A verse is labelled by its odd pādas: "paTyA" when both are pathyā, otherwise
    the vipulā of the first odd pāda that is not pathyā. The 8th syllable of each
    pāda is anceps and is not inspected.
    """
    if len(scans) != 4 or any(len(s) != 8 for s in scans):
        return None
    for s in scans:
        if s[1] == "L" and s[2] == "L":  # syllables 2–3 both laghu: forbidden
            return None
    # even pādas (2nd, 4th): 5–7 must be ja-gaṇa (L G L)
    for s in (scans[1], scans[3]):
        if s[4:7] != "LGL":
            return None
    forms = [_ODD_PADA_FORMS.get(s[4:7]) for s in (scans[0], scans[2])]
    if None in forms:
        return None
    return next((f for f in forms if f != "paTyA"), "paTyA")


def is_available() -> bool:
    return resolve_data_dir() is not None
