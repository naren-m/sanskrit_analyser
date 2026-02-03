"""Text normalization utilities for Sanskrit processing."""

import re

from sanskrit_analyzer.models.scripts import Script


# Character ranges for script detection
_DEVANAGARI_RANGE = re.compile(r"[\u0900-\u097F]")
_IAST_DIACRITICS = re.compile(r"[āīūṛṝḷḹēōṃḥñṅṇṭḍśṣ]", re.IGNORECASE)


def detect_script(text: str) -> Script:
    """Detect the script of Sanskrit text.

    Args:
        text: The Sanskrit text to analyze.

    Returns:
        The detected Script type.

    Examples:
        >>> detect_script("राम")
        Script.DEVANAGARI
        >>> detect_script("rāma")
        Script.IAST
        >>> detect_script("rAma")
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

    # Check for SLP1-specific patterns (uppercase vowels, specific consonants)
    # SLP1 uses: A I U R L M H for long vowels/anusvara/visarga
    # and specific letters like: w (ṭ), W (ṭh), q (ḍ), Q (ḍh), N (ṇ), S (ṣ), z (ś)
    slp1_markers = re.compile(r"[wWqQzSN]|[AIURLMH](?![a-z])")
    if slp1_markers.search(text):
        return Script.SLP1

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
