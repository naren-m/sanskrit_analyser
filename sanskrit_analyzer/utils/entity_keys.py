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

import functools
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


# --- Stem keys (#33) ---------------------------------------------------------
#
# ``canonical_key`` drops vowel length, so सगर (king Sagara) and सागर (ocean)
# share the key ``sagara`` and a graph merges them. The functions below key a
# name on its dictionary stem (prātipadika) from the vidyut kosha instead. The
# stem keeps vowel length and aspiration, and still folds case endings.

#: Anusvāra before a stop becomes that stop's class nasal (स्वयंभु → svayamBu),
#: the spelling the kosha indexes.
_CLASS_NASALS = (
    ("kKgG", "N"), ("cCjJ", "Y"), ("wWqQ", "R"), ("tTdD", "n"), ("pPbB", "m"),
)


def _kosha_form(name: str) -> str:
    """Any-script surface form → the SLP1 spelling the kosha indexes.

    The kosha stores word-final ``s`` and ``m``, not the visarga and anusvāra
    that written text uses. Without this step every visarga form misses
    (सागरः, वानरः).
    """
    from sanskrit_analyzer.utils.normalize import normalize_slp1

    form = normalize_slp1(normalize_brahmic(name.strip()))
    form = re.sub(r"M$", "m", form)
    form = re.sub(r"H$", "s", form)
    for stops, nasal in _CLASS_NASALS:
        form = re.sub(f"M(?=[{stops}])", nasal, form)
    return form


@functools.lru_cache(maxsize=50_000)
def lemma_keys(name: str, *, prefer_exact: bool = False) -> frozenset[str]:
    """The nominal stems (SLP1) the kosha gives for *name*.

    ``सागरम्``, ``सागरस्य`` and ``सागरः`` all return ``{"sAgara"}``;
    ``सगरेण`` returns ``{"sagara"}``. An ambiguous form returns every stem
    (``रम्भ`` → ``{"ramBa", "ramBA"}``).

    A stem that is a verb root is skipped. A participle's lemma is its root, so
    हर and हार would otherwise both carry ``hf`` and match.

    ``prefer_exact`` narrows the set to the form itself when the form is one of
    its own stems (``रम्भ`` → ``{"ramBa"}``). It separates gender pairs
    (रम्भ / रम्भा) at the cost of splitting stem / nominative pairs of one
    name (त्रिशिर / त्रिशिरा).

    Returns an empty set when the kosha has no entry (compounds, misspellings)
    or the kosha data is not installed. The caller chooses the fallback.
    """
    if not name.strip():
        return frozenset()
    from sanskrit_analyzer import vidyut_data

    try:
        form = _kosha_form(name)
        kosha = vidyut_data.kosha()
        entries = list(kosha.get(form))
        if form.endswith("o"):
            # Visarga sandhi writes -aḥ as -o before a voiced sound (हरयो,
            # रामो). Read it both ways; the union keeps the form ambiguous.
            entries += kosha.get(form[:-1] + "as")
    except Exception:  # missing data bundle, or a form vidyut cannot parse
        return frozenset()
    stems = set()
    for entry in entries:
        stem = getattr(entry, "pratipadika_entry", None)
        lemma = getattr(entry, "lemma", None)
        if stem is not None and lemma and getattr(stem, "dhatu_entry", None) is None:
            stems.add(lemma)
    if prefer_exact and form in stems:
        return frozenset({form})
    return frozenset(stems)


def lemma_keys_match(name_a: str, name_b: str, *, prefer_exact: bool = False) -> bool:
    """True when two names share a kosha stem.

    False when either name has no stem: "unknown" is not evidence of identity.
    """
    return bool(
        lemma_keys(name_a, prefer_exact=prefer_exact)
        & lemma_keys(name_b, prefer_exact=prefer_exact)
    )
