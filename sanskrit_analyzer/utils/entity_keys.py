"""Script- and case-folded entity keys for cross-scripture de-duplication (#393).

Collapses inflected / transliterated variants of a Sanskrit name (राम / रामः /
रामं / Rama) onto a single key, so a knowledge graph doesn't fragment one entity
into many nodes. Lifted from the Ramayanam knowledge-graph reader (#345/#352)
into the shared library so Yoga Sutras and other scripture apps reuse identical
folding rules.

The folding is deliberately lossy — it trades a small risk of over-merging
near-homographs for robust collapse of inflected/transliterated variants, which
is the dominant fragmentation mode in an extracted graph.
"""
from __future__ import annotations

import re
import unicodedata

from sanskrit_analyzer.utils.script_routing import normalize_brahmic, to_iast


def canonical_key(name: str) -> str:
    """A script- and case-folded key for entity de-duplication.

    Folds ``राम`` / ``रामः`` / ``रामं`` / ``Rama`` to the same key by:
      0. folding sibling Brahmic scripts onto Devanagari, so a name with (say)
         Gujarati characters spliced into Devanagari is not silently truncated
         by the whole-string transliteration in step 1,
      1. normalising to IAST,
      2. stripping combining diacritics (ā→a, ḥ→h, ṃ→m),
      3. lower-casing and keeping only ASCII letters,
      4. dropping a trailing visarga/anusvara case marker (``h``/``m``).
    """
    if not name:
        return ""
    s = to_iast(normalize_brahmic(name))
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = re.sub(r"[^a-z]", "", s.lower())
    s = re.sub(r"[hm]$", "", s)
    return s


def fold_virama(key: str) -> str:
    """Fold a word-final consonant+inherent-``a`` onto the bare consonant.

    A trailing virāma (halant) drops the inherent vowel, so ``हनुमान्`` romanises
    to ``hanumān`` (key ``hanuman``) while ``हनुमान`` romanises to ``hanumāna``
    (key ``hanumana``) — the *same* name split into two nodes purely by a trailing
    halant. Removing a trailing ``a`` (guarded by a length floor so a short key is
    never gutted) makes the two forms compare equal.
    """
    if len(key) > 3 and key.endswith("a"):
        return key[:-1]
    return key


def is_near_spelling_variant(key_a: str, key_b: str, *, min_length: int = 6) -> bool:
    """True when two canonical keys differ by a single *interior* character.

    Deliberately conservative — intended to collapse obvious mis-spellings such
    as ``विश्वामित्र`` (``visvamitra``) vs ``विश्रामित्र`` (``visramitra``) without
    over-merging genuinely distinct names. The guards:

    * both keys must be the same length (a pure substitution, never an
      insertion/deletion — those are far more likely different words, e.g.
      ``lakṣmaṇa`` vs ``lakṣaṇa``);
    * both keys must be at least *min_length* characters (short names like
      ``rama``/``kama`` must never fuzzy-merge);
    * exactly one position may differ, and it must be *interior* (first and last
      characters must match), ruling out unrelated names of equal length.
    """
    if not key_a or not key_b:
        return False
    if len(key_a) != len(key_b) or len(key_a) < min_length:
        return False
    diffs = [i for i, (x, y) in enumerate(zip(key_a, key_b)) if x != y]
    if len(diffs) != 1:
        return False
    i = diffs[0]
    return 0 < i < len(key_a) - 1


def keys_match(key_a: str, key_b: str) -> bool:
    """Fuzzy equality for canonical keys used by a graph de-duplicator.

    Returns True when the two keys are exactly equal, equal after folding a
    trailing halant/inherent-``a`` (:func:`fold_virama`), or a single-character
    interior variant (:func:`is_near_spelling_variant`). Exact-equality callers
    should test ``==`` first; this is the *fallback* comparison so near-variant
    folding never pre-empts an exact match.
    """
    if not key_a or not key_b:
        return False
    if key_a == key_b:
        return True
    if fold_virama(key_a) == fold_virama(key_b):
        return True
    return is_near_spelling_variant(key_a, key_b)
