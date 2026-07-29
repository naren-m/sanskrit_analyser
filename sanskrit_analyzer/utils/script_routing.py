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
import unicodedata

from sanskrit_analyzer.models.scripts import Script
from sanskrit_analyzer.utils.normalize import detect_script
from sanskrit_analyzer.utils.transliterate import transliterate

# Any character in the Devanagari Unicode block.
_DEVANAGARI = re.compile(r"[ऀ-ॿ]")

_DEVANAGARI_BLOCK = 0x0900
_BLOCK_SIZE = 0x80

# Brahmic blocks encoded with the *same* 128-slot layout as Devanagari, so a
# letter folds onto its Devanagari counterpart by pure codepoint arithmetic
# (Gujarati વ U+0AB5 and Devanagari व U+0935 both sit at offset 0x35).
# Sinhala (U+0D80) is deliberately excluded — its block does not share the
# layout, so offset arithmetic would produce garbage.
_SIBLING_BLOCKS = (
    0x0980,  # Bengali
    0x0A00,  # Gurmukhi
    0x0A80,  # Gujarati
    0x0B00,  # Oriya
    0x0B80,  # Tamil
    0x0C00,  # Telugu
    0x0C80,  # Kannada
    0x0D00,  # Malayalam
)


def _is_assigned(codepoint: int) -> bool:
    try:
        unicodedata.name(chr(codepoint))
    except ValueError:
        return False
    return True


def _build_brahmic_table() -> dict[int, str]:
    """Map every sibling-block codepoint onto its Devanagari counterpart.

    Only offsets assigned in *both* blocks are mapped. Scripts with a smaller
    inventory (Tamil has no voiced or aspirated series) leave those offsets
    unassigned, and an unassigned slot must stay untouched rather than be
    invented as some neighbouring letter.
    """
    table: dict[int, str] = {}
    for block in _SIBLING_BLOCKS:
        for offset in range(_BLOCK_SIZE):
            source, target = block + offset, _DEVANAGARI_BLOCK + offset
            if _is_assigned(source) and _is_assigned(target):
                table[source] = chr(target)
    return table


_BRAHMIC_TABLE = _build_brahmic_table()


def normalize_brahmic(text: str) -> str:
    """Fold sibling Brahmic scripts in *text* onto Devanagari, character by character.

    Devanagari and Latin pass through untouched, so this is safe to run over any
    string. The per-character mapping is what makes it useful on *mixed*-script
    text — a name like ``विश્વामित्र``, where two Gujarati characters have been
    spliced into an otherwise-Devanagari word, looks identical to ``विश्वामित्र``
    but shares no key with it. Whole-string transliteration cannot fix that: the
    string contains Devanagari, so it is transliterated *as* Devanagari and the
    foreign characters are silently dropped.

    Idempotent, and a no-op for text already in a single non-Brahmic script.
    """
    if not text:
        return text
    return text.translate(_BRAHMIC_TABLE)


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
