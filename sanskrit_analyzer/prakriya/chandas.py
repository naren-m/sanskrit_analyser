"""Chandas (meter) identification.

The default backend is a pure-Python engine ported from ``sanskrit_model``
(``slm.rules.ChandasEngine``). It needs no data bundle and covers the 145 named
vṛttas in data/meters-full.csv plus the rule-defined families no fixed table can
hold. A verse is tried in this order, most constrained first:

1. anuṣṭubh (śloka): 8-syllable pādas obeying the pathyā/vipulā rules;
2. samavṛtta: every pāda matches one CSV row (pāda-final syllable is anceps);
3. ardhasamavṛtta: pādas alternate between a multi-pāda row's patterns. Before
   upajāti: ākhyānikī is a specific indravajrā/upendravajrā alternation, and the
   specific name beats the generic free mix;
4. upajāti: pādas mix two rows that differ only in their first syllable;
5. jāti: only per-pāda mātrā totals are fixed (āryā). Last, because a mora rule
   is far looser than a syllable pattern and would shadow real vṛttas.

``vidyut.chandas`` is a second opinion only: when it is importable and its data
bundle resolves, a disagreeing name is recorded in ``ChandasResult.notes``. It
never changes the answer, and its absence never raises.

Anuṣṭubh rules (design doc §3.3.5): every pāda has 8 syllables; syllables 2-3
are never both laghu; even pādas take ja-gaṇa (L G L) at syllables 5-7 (the
pāda-final syllable is anceps); odd pādas take ya-gaṇa (L G G) -> pathyā, or one
of the four vipulā gaṇas na (LLL), bha (GLL), ma (GGG), ra (GLG).
"""
from __future__ import annotations

import csv
import logging
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from sanskrit_analyzer.vidyut_data import resolve_data_dir

logger = logging.getLogger(__name__)

_METERS_CSV = Path(__file__).resolve().parents[1] / "data" / "meters-full.csv"

# --- SLP1 syllable weight ---------------------------------------------------
# The library has no syllabifier, so this is the minimum ported from
# slm.rules.syllable_weights. Long vowels and e/E/o/O (SLP1 has no short e/o)
# are heavy by nature; avagraha is silent; spaces are not phonemes.
_LONG_VOWELS = frozenset("AIUFXeEoO")
_VOWELS = frozenset("aAiIuUfFxXeEoO")
_CONSONANTS = frozenset("kKgGNcCjJYwWqQRtTdDnpPbBmyrlvSzsh")
_NASAL_VISARGA = frozenset("MH")


def syllable_weights(text: str) -> str:
    """L/G string, one char per syllable of SLP1 ``text``.

    A syllable is guru when its vowel is long, when anusvara/visarga follows it,
    or when two or more consonants follow it before the next vowel. Everything
    up to the next vowel (across word breaks) belongs to the preceding syllable.
    """
    vowel_at = [i for i, ch in enumerate(text) if ch in _VOWELS]
    weights = []
    for n, v in enumerate(vowel_at):
        end = vowel_at[n + 1] if n + 1 < len(vowel_at) else len(text)
        coda = [ch for ch in text[v + 1:end] if ch != "'" and not ch.isspace()]
        heavy = (
            text[v] in _LONG_VOWELS
            or bool(coda and coda[0] in _NASAL_VISARGA)
            or sum(ch in _CONSONANTS for ch in coda) >= 2
        )
        weights.append("G" if heavy else "L")
    return "".join(weights)


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


@dataclass(frozen=True)
class _Row:
    name: str                  # name_slp1
    pattern: str               # CSV pattern: '|' yati marks, '/' pāda breaks
    padas: tuple[str, ...]     # clean per-pāda L/G patterns
    info: MeterInfo


@lru_cache(maxsize=1)
def _rows() -> tuple[_Row, ...]:
    with _METERS_CSV.open(encoding="utf-8") as fh:
        return tuple(
            _Row(
                name=row["name_slp1"],
                pattern=row["pattern"],
                padas=tuple(p for p in row["pattern"].replace("|", "").split("/") if p),
                info=MeterInfo(
                    name_iast=row["name_iast"],
                    name_deva=row["name_deva"],
                    syllables=int(row["syllables"]) if row["syllables"] else None,
                    ganas=row["ganas"],
                    yati=tuple(int(p) for p in row["yati_positions"].split(";") if p.strip()),
                ),
            )
            for row in csv.DictReader(fh)
        )


@lru_cache(maxsize=1)
def _meter_table() -> dict[str, list[tuple[str, MeterInfo]]]:
    """``name_slp1 -> [(pattern, info)]`` from data/meters-full.csv.

    The value is a list, not a single entry, because vidyut ships two distinct
    meters both named ``SrI`` - a 1-syllable one and an 11-syllable one. Keying
    by name alone would silently drop whichever came second.
    """
    table: dict[str, list[tuple[str, MeterInfo]]] = {}
    for row in _rows():
        table.setdefault(row.name, []).append((row.pattern, row.info))
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


# The śloka, upajāti and āryā are rule-defined, so they have no row in the
# vṛtta-only meters-full.csv and their names and display forms are supplied
# here. The anuṣṭubh pathyā/vipulā form stays in ``ChandasResult.name``.
_ANUSTUBH_INFO = MeterInfo(
    name_iast="anuṣṭubh",
    name_deva="अनुष्टुभ्",
    syllables=32,
    ganas="",
    yati=(),
)
_UPAJATI = "upajAti"
_ARYA = "AryA"
_ARYA_INFO = MeterInfo(name_iast="āryā", name_deva="आर्या", syllables=None, ganas="", yati=())

#: Moraic (jāti) meters as mātrā counts per pāda (guru = 2, laghu = 1). They fix
#: no syllable pattern, so they cannot live in meters-full.csv. Counts and the
#: matching approach follow the MIT-licensed github.com/sanskrit/chandas.
_JATIS: dict[str, tuple[int, int, int, int]] = {_ARYA: (12, 18, 12, 15)}


def _matches(weights: str, pattern: str, *, anceps_final: bool = True) -> bool:
    """Metrical match; the pāda-final syllable is anceps unless told otherwise."""
    if not weights or len(weights) != len(pattern):
        return False
    return weights == pattern or (anceps_final and weights[:-1] == pattern[:-1])


@lru_cache(maxsize=1)
def _upajati_families() -> dict[str, tuple[str, ...]]:
    """Shared tail (pattern minus first syllable) -> names of the meters that
    differ only in that syllable (indravajrā/upendravajrā, vaṃśastha/indravaṃśā)."""
    families: dict[str, list[str]] = {}
    for row in _rows():
        if len(row.padas) == 1:
            families.setdefault(row.padas[0][1:], []).append(row.name)
    return {tail: tuple(names) for tail, names in families.items() if len(names) > 1}


def _split_padas(line_weights: list[str], flat: str, lengths: list[int]) -> list[str]:
    """Pāda scans for a candidate meter whose pāda lengths cycle through ``lengths``.

    A verse is often typed as two half-lines, so unless it already has four
    lines it is cut from the flat scan by the meter's own pāda lengths.
    """
    if len(line_weights) != 4 and sum(lengths) == len(flat):
        cuts, padas = 0, []
        for n in lengths:
            padas.append(flat[cuts:cuts + n])
            cuts += n
        return padas
    return line_weights


def _vrtta(line_weights: list[str], flat: str, *, samavrtta: bool) -> _Row | None:
    """The first CSV row every pāda matches. Multi-pāda rows are matched
    cyclically: a 4-pāda verse checks pattern[0], pattern[1], pattern[0], ..."""
    for row in _rows():
        if (len(row.padas) == 1) is not samavrtta:
            continue
        lengths = [len(row.padas[i % len(row.padas)]) for i in range(4)]
        padas = _split_padas(line_weights, flat, lengths)
        # In an ardhasama row made of upajāti-family pādas (ākhyānikī), only the
        # even pādas' last syllable is anceps. With it free everywhere, a free
        # indravajrā/upendravajrā mix whose first syllables happen to alternate
        # would be named ākhyānikī. Other ardhasama rows keep it free on all pādas.
        strict_odd = not samavrtta and all(
            p[1:] in _upajati_families() for p in row.padas
        )
        if padas and all(
            _matches(
                w,
                row.padas[i % len(row.padas)],
                anceps_final=not strict_odd or i % 2 == 1,
            )
            for i, w in enumerate(padas)
        ):
            return row
    return None


def _upajati(line_weights: list[str], flat: str) -> tuple[list[str], int] | None:
    """(pāda scans, syllables per pāda) when pādas mix a family's first syllable.

    A verse whose pādas all open with the same weight is a pure vṛtta, not an
    upajāti, and is rejected here so the plain vṛtta match names it."""
    for tail in _upajati_families():
        padas = _split_padas(line_weights, flat, [len(tail) + 1] * 4)
        if len(padas) >= 2 and len({p[:1] for p in padas}) == 2 and all(
            _matches(p[1:], tail) for p in padas
        ):
            return padas, len(tail) + 1
    return None


def _is_jati(flat: str, name: str) -> bool:
    """Whether the flat scan can be cut at the jāti's cumulative mātrā totals.

    Pādas b and d may come up one mātrā short (a guru straddling the boundary),
    so both paths are tried."""
    totals: set[int] = set()
    running = 0
    for weight in flat:
        running += 2 if weight == "G" else 1
        totals.add(running)
    a, b, c, d = _JATIS[name]
    b, c, d = a + b, a + b + c, a + b + c + d
    if a not in totals:
        return False
    if b in totals and c in totals and running in (d, d - 1):
        return True
    return b - 1 in totals and c - 1 in totals and running in (d - 1, d - 2)


@lru_cache(maxsize=1)
def _classifier():
    """vidyut's classifier, or None when vidyut or its data bundle is absent."""
    data_dir = resolve_data_dir()
    if data_dir is None:
        return None
    try:
        from vidyut.chandas import Chandas

        return Chandas(str(data_dir / "chandas" / "meters.tsv"))
    except Exception as exc:  # vidyut is optional; a broken install must not break identify
        logger.warning("vidyut chandas unavailable: %s", exc)
        return None


def _vidyut_name(slp1_verse: str) -> str | None:
    classifier = _classifier()
    if classifier is None:
        return None
    try:
        padya = classifier.classify(slp1_verse.replace(".", " ")).padya
    except BaseException as exc:  # noqa: BLE001 - pyo3 PanicException is a BaseException
        if isinstance(exc, (KeyboardInterrupt, SystemExit)):
            raise
        # second opinion only; never fail the default path
        logger.warning("vidyut chandas classify failed: %s", exc)
        return None
    return str(padya) if padya is not None else None


def _with_second_opinion(result: ChandasResult, slp1_verse: str) -> ChandasResult:
    """Note vidyut's name when it disagrees. A fuzzy jāti match of vidyut's is
    only worth noting when we found nothing; a name our table carries is an
    exact vṛtta template and always worth noting."""
    other = _vidyut_name(slp1_verse)
    if other is None or other == result.name:
        return result
    if result.name is not None and other not in _meter_table():
        return result
    notes = f"{result.notes}; " if result.notes else ""
    return ChandasResult(
        name=result.name,
        scans=result.scans,
        notes=f"{notes}vidyut suggests {other}",
        info=result.info,
    )


def identify(slp1_verse: str) -> ChandasResult:
    # SLP1 is ASCII. Anything else is a character transliteration left behind
    # (nukta, ZWJ, om, curly quotes). They carry no syllable weight, and
    # vidyut's second opinion indexes a 256-entry table and panics on them.
    slp1_verse = "".join(ch for ch in slp1_verse if ch.isascii())
    # dandas (".") and newlines separate lines; spaces separate words.
    lines = [ln.strip() for ln in re.split(r"[.\n]+", slp1_verse) if ln.strip()]
    line_weights = [w for w in (syllable_weights(ln) for ln in lines) if w]
    flat = "".join(line_weights)
    # Below one pāda's worth of syllables a "meter" is noise.
    if len(flat) < 8:
        return ChandasResult(name=None, scans=line_weights, notes="too short for meter")
    result = _scan(line_weights, flat)
    return _with_second_opinion(result, slp1_verse)


def _scan(line_weights: list[str], flat: str) -> ChandasResult:
    if len(flat) == 32:
        scans = [flat[i:i + 8] for i in range(0, 32, 8)]
        if form := anushtubh_form(scans):
            return ChandasResult(
                name=f"anuzwuB ({form})", scans=scans, info=_ANUSTUBH_INFO
            )
    if row := _vrtta(line_weights, flat, samavrtta=True):
        scans = _split_padas(line_weights, flat, [len(row.padas[0])] * 4)
        return ChandasResult(row.name, scans, info=meter_info(row.name, scans))
    if row := _vrtta(line_weights, flat, samavrtta=False):
        scans = _split_padas(
            line_weights, flat, [len(row.padas[i % len(row.padas)]) for i in range(4)]
        )
        return ChandasResult(row.name, scans, info=meter_info(row.name, scans))
    if found := _upajati(line_weights, flat):
        scans, size = found
        info = MeterInfo("upajāti", "उपजाति", size, "", ())
        return ChandasResult(_UPAJATI, scans, info=info)
    if any(_is_jati(flat, name) for name in _JATIS):
        return ChandasResult(_ARYA, line_weights, info=_ARYA_INFO)
    return ChandasResult(
        name=None, scans=line_weights, notes="no meter matched (prose or corrupt text?)"
    )


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
    """The default engine is pure Python and always available."""
    return True
