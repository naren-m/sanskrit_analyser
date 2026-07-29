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
from sanskrit_analyzer.utils.normalize import detect_script
from sanskrit_analyzer.utils.transliterate import transliterate

# Any character in the Devanagari Unicode block.
_DEVANAGARI = re.compile(r"[ऀ-ॿ]")


def is_devanagari(text: str) -> bool:
    """True when *text* contains any Devanagari character."""
    return bool(text and _DEVANAGARI.search(text))


def to_devanagari(text: str) -> str:
    """Return *text* in Devanagari, auto-detecting the source script.

    The source script (Devanagari / IAST / SLP1) is detected per
    :func:`detect_script` rather than assumed. The previous "everything
    non-Devanagari is SLP1" shortcut mangled IAST input — feeding "yogaḥ"
    through an SLP1->Devanagari pass left the visarga untranslated
    ("योगḥ" instead of "योगः").
    """
    if not text:
        return text
    source = detect_script(text)
    if source == Script.DEVANAGARI:
        return text
    return transliterate(text, source, Script.DEVANAGARI)


def to_iast(text: str) -> str:
    """Return *text* in IAST, auto-detecting the source script.

    Devanagari and SLP1 are transliterated; text already in IAST (or a plain
    Latin spelling) is returned unchanged. SLP1 shares the Latin range, so the
    old is-it-Devanagari check let SLP1 pass through undecoded ("yogaH" stayed
    "yogaH" instead of becoming "yogaḥ").
    """
    if not text:
        return text
    source = detect_script(text)
    if source == Script.IAST:
        return text
    return transliterate(text, source, Script.IAST)
