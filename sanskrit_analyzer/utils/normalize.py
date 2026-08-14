"""Text normalization utilities for Sanskrit processing."""

import re

from sanskrit_analyzer.models.scripts import Script


# Character ranges for script detection
_DEVANAGARI_RANGE = re.compile(r"[\u0900-\u097F]")
_IAST_DIACRITICS = re.compile(r"[āīūṛṝḷḹēōṃḥñṅṇṭḍśṣ]", re.IGNORECASE)
# SLP1-exclusive lowercase letters, or any interior uppercase (see detect_script).
_SLP1_MARKERS = re.compile(r"[fxzwq]|(?<=[A-Za-z])[A-Z]")


def detect_script(text: str, plain_ascii_default: Script | None = None) -> Script:
    """Detect the script of Sanskrit text.

    This is a Sanskrit-domain heuristic. It assumes the input is Sanskrit in
    one of Devanagari, IAST, or SLP1, and may misclassify text that is not
    (e.g. plain English, camelCase identifiers, or Harvard-Kyoto, which shares
    SLP1's capital-letter conventions). Full Harvard-Kyoto support is out of
    scope; HK input may be read as SLP1.

    Args:
        text: The Sanskrit text to analyze.
        plain_ascii_default: Script to assume when the text is plain ASCII
            with no unambiguous markers (no Devanagari, no IAST diacritics,
            no SLP1-exclusive letters or interior capitals). Title-case SLP1
            like "Bavati" is indistinguishable from an IAST proper noun like
            "Rama"; callers that know their input's script (e.g. engines fed
            already-normalized SLP1 by the ensemble) use this to resolve the
            ambiguity. None keeps the historical IAST fallback.

    Returns:
        The detected Script type.

    Examples:
        >>> detect_script("राम")
        Script.DEVANAGARI
        >>> detect_script("rāma")
        Script.IAST
        >>> detect_script("rAma")  # plain ASCII, no SLP1 markers -> IAST
        Script.IAST
        >>> detect_script("gacCati")  # mid-word capital aspirate -> SLP1
        Script.SLP1
    """
    if not text.strip():
        return Script.SLP1  # Default for empty text

    # Check for Devanagari characters
    if _DEVANAGARI_RANGE.search(text):
        return Script.DEVANAGARI

    # Check for IAST diacritics
    if _IAST_DIACRITICS.search(text):
        return Script.IAST

    # Acronym / all-caps guard: SLP1 capitals are single transliteration letters
    # always interspersed with lowercase, so a run of 3+ consecutive ASCII
    # uppercase letters indicates an English acronym (JSON, USA, KGB), never SLP1.
    # (A 2-run like the visarga+consonant in "duHKa" is legitimate SLP1, so the
    # threshold is 3, not 2.) Skip the SLP1 heuristic in that case so acronyms are
    # not misrouted to SLP1 by the interior-uppercase rule below.
    has_caps_run = re.search(r"[A-Z]{3,}", text) is not None

    # Check for SLP1-specific patterns. SLP1 encodes retroflexes, sibilants,
    # aspirates, long vowels and anusvara/visarga with letters plain-ASCII IAST
    # never uses:
    #   - lowercase letters exclusive to SLP1: f (ṛ), x (ḷ), z (ś), w (ṭ), q (ḍ)
    #   - interior uppercase: SLP1 uses capitals mid-word (A/I/U long vowels, M/H
    #     anusvara/visarga, aspirate/retroflex/nasal consonants). IAST may
    #     capitalize a word's first letter but never uses interior capitals, so
    #     requiring the uppercase to be preceded by a letter avoids flagging IAST
    #     proper nouns like "Rama". This is why the old `(?![a-z])` lookahead was
    #     wrong: it rejected the common case of a marker followed by a lowercase
    #     letter (e.g. "rAma", "gacCati"), silently misrouting SLP1 to IAST.
    if not has_caps_run and _SLP1_MARKERS.search(text):
        return Script.SLP1

    # Plain ASCII with no script markers is ambiguous; honor the caller's hint.
    if plain_ascii_default is not None:
        return plain_ascii_default

    # Default to IAST for plain ASCII that might be simplified transliteration
    return Script.IAST


def normalize_slp1(text: str, source_script: Script | None = None) -> str:
    """Normalize Sanskrit text to SLP1 script.

    This is the standard normalization for internal processing.
    The function auto-detects the source script if not provided.

    Args:
        text: The Sanskrit text in any supported script.
        source_script: The source script. If None, auto-detected.

    Returns:
        The text normalized to SLP1.

    Examples:
        >>> normalize_slp1("राम")
        'rAma'
        >>> normalize_slp1("rāma")
        'rAma'
        >>> normalize_slp1("rAma", Script.SLP1)
        'rAma'
    """
    from sanskrit_analyzer.utils.transliterate import transliterate

    if not text.strip():
        return text

    if source_script is None:
        source_script = detect_script(text)

    if source_script == Script.SLP1:
        return text

    return transliterate(text, source_script, Script.SLP1)


def normalize_whitespace(text: str) -> str:
    """Normalize whitespace in text.

    Collapses multiple spaces to single space and strips leading/trailing whitespace.

    Args:
        text: The text to normalize.

    Returns:
        Text with normalized whitespace.
    """
    return " ".join(text.split())


def remove_punctuation(text: str) -> str:
    """Remove common punctuation from Sanskrit text.

    Removes dandas (।॥), digits, and common punctuation while preserving
    the Sanskrit characters.

    Args:
        text: The text to process.

    Returns:
        Text with punctuation removed.
    """
    # Remove dandas
    text = re.sub(r"[।॥]", " ", text)
    # Remove digits (both Devanagari and ASCII)
    text = re.sub(r"[\u0966-\u096F0-9]", "", text)
    # Remove common punctuation
    text = re.sub(r"[,.\-;:!?\"'()[\]{}]", "", text)
    return normalize_whitespace(text)
