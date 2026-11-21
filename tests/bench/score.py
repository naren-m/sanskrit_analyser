"""Scoring helpers for the bench. All matching is on SLP1."""
from __future__ import annotations

import re

from sanskrit_analyzer.reader.sandhi import vowel_join as _vowel_join

_VOICING = str.maketrans({"g": "k", "d": "t", "b": "p", "D": "T", "B": "P", "G": "K"})

# Longest run of output tokens that may join to one gold pada (compound members).
_MAX_RUN = 6


def norm_slp1(word: str) -> str:
    """SLP1 key with sandhi *spelling* folded away.

    Anusvāra vs m (and vs the class nasal before a consonant), the visarga surfaces (ḥ / s / r, and -o for -aḥ) and
    final-consonant voicing (vāg / vāk) differ between running text and the
    gloss line without being different words.
    """
    s = re.sub(r"[^A-Za-z]", "", word or "")
    s = s.replace("M", "m")
    # A nasal before a consonant is one sound spelled two ways: anusvāra or the
    # class nasal (dvaMdva / dvandva, saMtuzwa / santuzwa). Fold both to m.
    s = re.sub(r"[NYRn](?=[kKgGcCjJwWqQtTdDpPbBSzsh])", "m", s)
    s = re.sub(r"o$", "aH", s)
    s = re.sub(r"[srSz]$", "H", s)
    return s.translate(_VOICING)


def recovered(gold: list[str], tokens: list[str]) -> int:
    """Count gold padas matched by a contiguous run of output tokens.

    A finer split of a compound than the gloss is not penalised: members are
    joined both verbatim and with vowel sandhi. A merge across a pada
    boundary, or a cut inside one, is penalised.
    """
    toks = [t for t in (re.sub(r"[^A-Za-z]", "", t) for t in tokens) if t]
    runs: set[str] = set()
    for i in range(len(toks)):
        plain = joined = ""
        for j in range(i, min(i + _MAX_RUN, len(toks))):
            plain += toks[j]
            joined = _vowel_join(joined, toks[j])
            runs.update((norm_slp1(plain), norm_slp1(joined)))
    return sum(1 for g in gold if norm_slp1(g) in runs)


def meter_match(got: str | None, gold: str) -> bool:
    """Exact meter name, or any variant of a bare family name in the gold."""
    if not got:
        return False
    return got == gold or got.startswith(gold + " ")
