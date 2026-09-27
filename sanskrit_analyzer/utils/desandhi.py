"""Undo common word-final sandhi on an SLP1 form to get kosha lookup keys.

Pure string logic, no vidyut. Shared by ``dhatu`` and ``prakriya``, which
must not import each other.
"""
from __future__ import annotations

import re

# Stop (sparśa) -> the nasal of its varga. Printed texts write a word-internal
# nasal before a stop as anusvāra (शंकर, पुंगव, चंद्र) while the kosha keys the
# homorganic nasal (SaNkara, puNgava, candra).
_VARGA_NASAL = {
    **dict.fromkeys("kKgG", "N"),
    **dict.fromkeys("cCjJ", "Y"),
    **dict.fromkeys("wWqQ", "R"),
    **dict.fromkeys("tTdD", "n"),
    **dict.fromkeys("pPbB", "m"),
}
_ANUSVARA_BEFORE_STOP = re.compile(r"M(?=[kKgGcCjJwWqQtTdDpPbB])")


def _homorganic(slp: str) -> str:
    return _ANUSVARA_BEFORE_STOP.sub(lambda m: _VARGA_NASAL[slp[m.end()]], slp)


def desandhi_candidates(slp: str) -> list[str]:
    """Generate lookup candidates for a SLP1 form, undoing common final sandhi.

    Two facts force this. (1) Kosha is keyed by the underlying ``-s``/``-r``/stem
    form, not the pausal visarga ``-H``. (2) In *running* verse text a word-final
    visarga has already mutated by sandhi — ``-aḥ`` → ``-o`` before a voiced
    sound (रामः → रामो), visarga → ``ś``/``ṣ`` before sibilants, final ``m`` →
    anusvāra ``ṃ``. Without reversing these, almost nothing in connected text
    resolves. Each candidate is also tried with a word-internal anusvāra before
    a stop written as its homorganic nasal. Order is preserved and
    de-duplicated.
    """
    out = [slp]
    if slp:
        stem, last = slp[:-1], slp[-1]
        if last == "H":  # visarga (pausa) -> -as / -ar
            out += [stem + "s", stem + "r"]
        elif last == "o":  # -aḥ / -as -> -o before voiced (रामो, महावीर्यो)
            out += [stem + "as", stem + "aH", stem + "a"]
        elif last in ("S", "z"):  # visarga -> ś / ṣ before c-/ṭ-
            out += [stem + "H", stem + "s"]
        elif last == "M":  # final m -> anusvāra ṃ
            out += [stem + "m"]
    # Spelling variant, not sandhi: try each candidate with the nasal restored.
    out += [_homorganic(c) for c in out]
    seen: set[str] = set()
    uniq: list[str] = []
    for c in out:
        if c and c not in seen:
            seen.add(c)
            uniq.append(c)
    return uniq


# Backwards-compatible alias (the function used to only handle visarga).
visarga_candidates = desandhi_candidates
