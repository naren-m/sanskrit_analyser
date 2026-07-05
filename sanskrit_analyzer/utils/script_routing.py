"""Auto-detecting script routing for Sanskrit text (issue #393).

The lower-level :func:`sanskrit_analyzer.utils.transliterate.transliterate`
requires an *explicit* source script. These helpers auto-detect the common case
so callers holding mixed-script corpus text — some verses already in Devanagari,
others in SLP1, entity names sometimes in plain Latin — don't have to branch on
the script themselves.

Lifted from the Ramayanam knowledge-graph reader so every scripture app shares
one implementation (cf. the ``sanskrit_analyzer`` single-source policy).

NOTE: ``to_devanagari`` / ``to_iast`` here intentionally shadow the same-named
*two-argument* functions in :mod:`sanskrit_analyzer.utils.transliterate`. They
are therefore NOT re-exported under those names at the ``sanskrit_analyzer.utils``
package surface; import the auto-detecting variants from this submodule
explicitly::

    from sanskrit_analyzer.utils.script_routing import to_devanagari, to_iast
"""
from __future__ import annotations

import re

from sanskrit_analyzer.models.scripts import Script
from sanskrit_analyzer.utils.transliterate import transliterate

# Any character in the Devanagari Unicode block.
_DEVANAGARI = re.compile(r"[ऀ-ॿ]")


def is_devanagari(text: str) -> bool:
    """True when *text* contains any Devanagari character."""
    return bool(text and _DEVANAGARI.search(text))


def to_devanagari(text: str) -> str:
    """Return *text* in Devanagari, auto-detecting the source script.

    Already-Devanagari text is returned unchanged; otherwise the text is treated
    as SLP1 and transliterated. This is the script most Sanskrit analyzers
    segment reliably.
    """
    if not text or is_devanagari(text):
        return text
    return transliterate(text, Script.SLP1, Script.DEVANAGARI)


def to_iast(text: str) -> str:
    """Return *text* in IAST, auto-detecting the source script.

    Devanagari is transliterated; Latin text (already IAST, or a plain-English
    spelling) is returned unchanged.
    """
    if not text:
        return text
    if is_devanagari(text):
        return transliterate(text, Script.DEVANAGARI, Script.IAST)
    return text
