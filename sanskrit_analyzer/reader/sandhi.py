"""Minimal vowel sandhi for re-joining split words (6.1.77, 6.1.87-88, 6.1.101)."""
from __future__ import annotations

import csv
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

# Vowel sandhi at a compound-member boundary: (last of left, first of right) -> joined.
_SAVARNA = {"a": "A", "i": "I", "u": "U", "f": "F"}
_SHORT = {"A": "a", "I": "i", "U": "u", "F": "f"}
_GUNA_VRDDHI = {"i": "e", "u": "o", "f": "ar", "e": "E", "E": "E", "o": "O", "O": "O"}
_YAN = {"i": "y", "u": "v", "f": "r"}
_VOWELS = set("aAiIuUfFeEoO")


def vowel_join(left: str, right: str) -> str:
    """Join two compound members with the common vowel sandhi rules."""
    if not left or not right or left[-1] not in _VOWELS or right[0] not in _VOWELS:
        return left + right
    x, y = _SHORT.get(left[-1], left[-1]), _SHORT.get(right[0], right[0])
    head, tail = left[:-1], right[1:]
    if x == y and x in _SAVARNA:            # 6.1.101 akaH savarRe dIrghaH
        return head + _SAVARNA[x] + tail
    if x == "a" and y in _GUNA_VRDDHI:       # 6.1.87 Ad guRaH, 6.1.88 vfdDir eci
        return head + _GUNA_VRDDHI[y] + tail
    if x in _YAN:                            # 6.1.77 iko yaR aci
        return head + _YAN[x] + right
    return left + right


# --- Rule-table re-join and split validation (issue #75, phase A) -----------------
_DATA = Path(__file__).resolve().parent.parent / "data"
_RULE_FILES = ("sandhi-rules-full.csv", "sandhi-rules-extra.csv")
MAX_SURFACES = 512  # cap on partial joins kept per junction, so output cannot explode


@dataclass(frozen=True)
class Junction:
    """One pada boundary: the rule row used, or ``rule=None`` for a verbatim join."""
    first: str
    second: str
    result: str
    sutra: str | None
    rule: str | None


@dataclass(frozen=True)
class Rejoin:
    """A licensed surface and the junction choices that produced it."""
    surface: str
    junctions: tuple[Junction, ...]


@dataclass(frozen=True)
class Licence:
    """Verdict of ``split_is_licensed``: ``rejoin`` is the matching join, if any."""
    ok: bool
    rejoin: Rejoin | None
    unruled: tuple[Junction, ...]


@lru_cache(maxsize=1)
def _rules() -> dict[str, tuple[dict[str, str], ...]]:
    """Rule rows from both CSVs, indexed by the last letter of ``first_slp1``."""
    by_last: dict[str, list[dict[str, str]]] = {}
    for name in _RULE_FILES:
        with (_DATA / name).open(encoding="utf-8") as fh:
            for row in csv.DictReader(fh):
                if row["first_slp1"] and row["second_slp1"]:
                    by_last.setdefault(row["first_slp1"][-1], []).append(row)
    return {k: tuple(v) for k, v in by_last.items()}


def _options(left: str, right: str, left_room: int, right_room: int):
    """Yield (cut_left, text, cut_right, junction) for each rule row fitting the junction.

    A final visarga on ``left`` matches as ``s``. ``left_room`` / ``right_room`` are the
    letters of each pada not already consumed by a neighbouring junction.
    """
    norm = left[:-1] + "s" if left.endswith("H") else left
    seen = set()
    for row in _rules().get(norm[-1:], ()):
        f, s = row["first_slp1"], row["second_slp1"]
        if len(f) > left_room or len(s) > right_room:
            continue
        if norm.endswith(f) and right.startswith(s) and (f, s, row["result_slp1"]) not in seen:
            seen.add((f, s, row["result_slp1"]))
            yield (norm, len(f), row["result_slp1"], len(s),
                   Junction(f, s, row["result_slp1"], row["sutra"], row["sandhi_name"]))


def rejoin(padas: list[str]) -> list[Rejoin]:
    """Join adjacent SLP1 padas with the rule table; return every licensed surface.

    Each rule row matching a junction (suffix of the left pada, prefix of the right)
    gives its own result. A junction with no row joins verbatim, marked ``rule=None``.
    Partial joins are deduped and capped at ``MAX_SURFACES``.
    """
    padas = [p for p in padas if p]
    if not padas:
        return []
    # state: (surface so far, junctions, letters of padas[i] already consumed on the left)
    states: list[tuple[str, tuple[Junction, ...], int]] = [("", (), 0)]
    for i in range(len(padas) - 1):
        left, right = padas[i], padas[i + 1]
        nxt: dict[tuple[str, int], tuple[Junction, ...]] = {}
        for prefix, js, cut_r in states:
            room = len(left) - cut_r
            opts = list(_options(left, right, room, len(right)))
            for norm, cut_l, text, cut_next, j in opts:
                key = (prefix + norm[cut_r:len(norm) - cut_l] + text, cut_next)
                nxt.setdefault(key, js + (j,))
            if not opts:
                key = (prefix + left[cut_r:], 0)
                nxt.setdefault(key, js + (Junction(left, right, left + right, None, None),))
        states = [(k[0], js, k[1]) for k, js in list(nxt.items())[:MAX_SURFACES]]
    out: dict[str, Rejoin] = {}
    for prefix, js, cut_r in states:
        surface = prefix + padas[-1][cut_r:]
        out.setdefault(surface, Rejoin(surface, js))
    return list(out.values())


def _fold(s: str) -> str:
    """Drop spaces, avagraha and punctuation, and the final visarga (or its s/r source)."""
    return re.sub(r"[^A-Za-z]", "", s).rstrip("Hsr")


def split_is_licensed(text_slp1: str, padas: list[str]) -> Licence:
    """True when some ``rejoin(padas)`` surface equals the input after folding.

    Folding removes spaces, avagraha and the final visarga on both sides.
    ``unruled`` lists the junctions that joined verbatim (no rule row) in the
    matching join, or in the first join when none matches.
    """
    target = _fold(text_slp1)
    joins = rejoin(padas)
    for r in joins:
        if _fold(r.surface) == target:
            return Licence(True, r, tuple(j for j in r.junctions if j.rule is None))
    unruled = tuple(j for j in joins[0].junctions if j.rule is None) if joins else ()
    return Licence(False, None, unruled)
