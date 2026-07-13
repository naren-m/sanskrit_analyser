"""Chandas (meter) identification.

``vidyut.chandas`` handles fixed-template vṛttas via meters.tsv. The śloka
(anuṣṭubh) is NOT a fixed L/G template, so when vidyut finds no match we apply
the classical pathyā/vipulā checks ourselves (design doc §3.3.5):

* every pāda has 8 syllables;
* syllables 2–3 are never both laghu;
* syllable 5 is laghu and 6 is guru (pāda-final syllable is anceps);
* syllable 7: guru in odd pādas -> pathyā; other odd-pāda shapes -> vipulā.
  Even pādas always need 7th laghu (ja-gaṇa at 5–7).
"""
from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache

from sanskrit_analyzer.deep_read.kosha_engine import VidyutUnavailable, resolve_data_dir


@dataclass(frozen=True)
class ChandasResult:
    name: str | None        # e.g. "mandAkrAntA", "anuzwuB (paTyA)"
    scans: list[str]        # per-pāda weight strings, e.g. "GGLG..."
    notes: str | None = None


@lru_cache(maxsize=1)
def _classifier():
    data_dir = resolve_data_dir()
    if data_dir is None:
        raise VidyutUnavailable("vidyut data bundle not found; chandas unavailable.")
    from vidyut.chandas import Chandas

    return Chandas(str(data_dir / "chandas" / "meters.tsv"))


def identify(slp1_verse: str) -> ChandasResult:
    match = _classifier().classify(slp1_verse.replace(".", " "))
    scans = [
        "".join(str(a.weight) for a in row) for row in (match.aksharas or [])
    ]
    # vidyut fuzzy-matches even tiny fragments (5 syllables of prose match a
    # short vṛtta); below one pāda's worth of syllables a "meter" is noise.
    if sum(len(s) for s in scans) < 8:
        return ChandasResult(name=None, scans=scans, notes="too short for meter")
    if match.padya is not None:
        return ChandasResult(name=str(match.padya), scans=scans)
    form = anushtubh_form(_as_four_padas(scans))
    if form:
        return ChandasResult(name=f"anuzwuB ({form})", scans=scans)
    return ChandasResult(
        name=None, scans=scans, notes="no meter matched (prose or corrupt text?)"
    )


def _as_four_padas(scans: list[str]) -> list[str]:
    """vidyut may scan a śloka as one row of 32 or 2×16; split to 4×8 pādas."""
    if len(scans) == 1 and len(scans[0]) == 32:
        s = scans[0]
        return [s[0:8], s[8:16], s[16:24], s[24:32]]
    if len(scans) == 2 and all(len(s) == 16 for s in scans):
        return [scans[0][:8], scans[0][8:], scans[1][:8], scans[1][8:]]
    return scans


def anushtubh_form(scans: list[str]) -> str | None:
    """Return "paTyA"/"vipulA" if the 4 pāda scans satisfy śloka rules, else None."""
    if len(scans) != 4 or any(len(s) != 8 for s in scans):
        return None
    for s in scans:
        if s[1] == "L" and s[2] == "L":  # syllables 2–3 both laghu: forbidden
            return None
    # even pādas (2nd, 4th): 5–7 must be ja-gaṇa (L G L)
    for s in (scans[1], scans[3]):
        if s[4:7] != "LGL":
            return None
    # odd pādas: 5=L, 6=G required; 7=G -> pathyā, else vipulā
    for s in (scans[0], scans[2]):
        if s[4] != "L" or s[5] != "G":
            return "vipulA"  # vipulā variants relax 5–7; be permissive but labeled
    if all(s[6] == "G" for s in (scans[0], scans[2])):
        return "paTyA"
    return "vipulA"


def is_available() -> bool:
    return resolve_data_dir() is not None
