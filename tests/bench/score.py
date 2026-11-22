"""Scoring helpers for the bench. All matching is on SLP1."""
from __future__ import annotations

import re

from sanskrit_analyzer.dhatu.dhatupatha import strip_anubandhas
from sanskrit_analyzer.reader.sandhi import vowel_join as _vowel_join

_VOICING = str.maketrans({"g": "k", "d": "t", "b": "p", "D": "T", "B": "P", "G": "K"})

# Longest run of output tokens that may join to one gold pada (compound members).
_MAX_RUN = 6


# Anusvāra before a stop is that stop's class nasal (puMgava == puNgava).
_CLASS_NASAL = {c: n for cls, n in (("kKgG", "N"), ("cCjJ", "Y"), ("wWqQ", "R"),
                                    ("tTdD", "n"), ("pPbB", "m")) for c in cls}

# Particles that sandhi onto a preceding pada (putrASca = putrAH + ca).
_ENCLITICS = ("ca", "tu", "iva", "eva", "api")


def _nasal_fold(s: str) -> str:
    """M or m before a stop becomes that stop's class nasal (assimilated nasal)."""
    return re.sub(r"[Mm](?=[kKgGcCjJwWqQtTdDpPbB])", lambda m: _CLASS_NASAL[s[m.end()]], s)


def _lemma_key(lemma: str) -> str:
    """Narrow lemma key: letters only plus the nasal fold. No voicing or visarga folds."""
    return _nasal_fold(re.sub(r"[^A-Za-z]", "", lemma or "")).replace("M", "m")


def norm_slp1(word: str, legacy: bool = False) -> str:
    """SLP1 key with sandhi *spelling* folded away.

    Anusvāra vs m (or the class nasal before a stop), the visarga surfaces
    (ḥ / s / r, and -o for -aḥ) and final-consonant voicing (vāg / vāk) differ
    between running text and the gloss line without being different words.
    ``legacy`` keeps the pre-#96 fold (every M -> m) for ``--legacy-score``.
    """
    s = re.sub(r"[^A-Za-z]", "", word or "")
    if not legacy:
        s = _nasal_fold(s)
    s = s.replace("M", "m")
    s = re.sub(r"o$", "aH", s)
    s = re.sub(r"[srSz]$", "H", s)
    return s.translate(_VOICING)


def _key(word: str) -> str:
    """norm_slp1 with the final visarga dropped: pausal ``sa`` matches ``saH``."""
    return norm_slp1(word)[:-1] if norm_slp1(word).endswith("H") else norm_slp1(word)


def _letters(tokens: list[str]) -> list[str]:
    return [t for t in (re.sub(r"[^A-Za-z]", "", t) for t in tokens) if t]


def _targets(gold: str) -> list[tuple[str, str | None]]:
    """(key, enclitic that must follow) pairs a gold pada may be recovered as."""
    out: list[tuple[str, str | None]] = [(_key(gold), None)]
    g = re.sub(r"[^A-Za-z]", "", gold)
    for e in _ENCLITICS:
        if g.endswith(e) and len(g) > len(e):
            stem = g[: -len(e)]
            out.append((_key(stem), e))
            # Final -n before c/t surfaces as -MS / -Ms (kIrtimAMSca = kIrtimAn ca).
            if stem.endswith(("MS", "Ms")):
                out.append((_key(stem[:-2] + "n"), e))
    # -aH + api -> -o'pi (so'pi = saH api); the avagraha is already stripped.
    if g.endswith("opi") and len(g) > 3:
        out.append((_key(g[:-3] + "aH"), "api"))
    return out


def recovered(gold: list[str], tokens: list[str], legacy: bool = False) -> int:
    """Count gold padas matched by a contiguous run of output tokens.

    A finer split of a compound than the gloss is not penalised: members are
    joined both verbatim and with vowel sandhi. A merge across a pada
    boundary, or a cut inside one, is penalised. A final visarga may be
    present or absent, and a gold pada glued to an enclitic is also matched
    by the two parts. ``legacy`` is the pre-#96 matcher.
    """
    toks = _letters(tokens)
    if legacy:
        runs: set[str] = set()
        for i in range(len(toks)):
            plain = joined = ""
            for j in range(i, min(i + _MAX_RUN, len(toks))):
                plain += toks[j]
                joined = _vowel_join(joined, toks[j])
                runs.update((norm_slp1(plain, True), norm_slp1(joined, True)))
        return sum(1 for g in gold if norm_slp1(g, True) in runs)
    return sum(1 for g in gold if _candidates(g, [(t, None) for t in toks]) is not None)


def _candidates(gold: str, toks: list[tuple[str, str | None]]) -> list[str | None] | None:
    """Lemmas offered by every run of ``toks`` that recovers ``gold``.

    None when no run matches. Each match offers the run's last-member lemma
    and the joined member lemmas (the compound stem).
    """
    surf = [re.sub(r"[^A-Za-z]", "", t[0]) for t in toks]
    targets = _targets(gold)
    found: list[str | None] | None = None
    for i in range(len(toks)):
        plain = joined = ""
        stems: list[str] | None = ["", ""]
        for j in range(i, min(i + _MAX_RUN, len(toks))):
            plain += surf[j]
            joined = _vowel_join(joined, surf[j])
            lemma = toks[j][1]
            if lemma is None or stems is None:
                stems = None
            else:
                lem = re.sub(r"[^A-Za-z]", "", lemma)
                stems = [stems[0] + lem, _vowel_join(stems[1], lem)]
            keys = {_key(plain), _key(joined)}
            for key, enc in targets:
                if key in keys and (enc is None or (
                        j + 1 < len(toks) and norm_slp1(surf[j + 1]) == norm_slp1(enc))):
                    found = (found or []) + [lemma] + (stems or [])
    return found


def lemma_match(gold: str, toks: list[tuple[str, str | None]], accepted: set[str]) -> bool:
    """True when a run of output tokens recovers ``gold`` with an accepted lemma.

    Verb lemmas are upadeśas (``gamx~``), so they also match after anubandha
    stripping. Lemmas compare under ``_lemma_key`` (nasal fold only, so lemmas
    differing in voicing or a final sibilant stay distinct words).
    """
    want = {_lemma_key(a) for a in accepted}
    return any(
        got is not None and (_lemma_key(got) in want or _lemma_key(strip_anubandhas(got)) in want)
        for got in _candidates(gold, toks) or []
    )


def meter_match(got: str | None, gold: str) -> bool:
    """Exact meter name, or any variant of a bare family name in the gold."""
    if not got:
        return False
    return got == gold or got.startswith(gold + " ")
