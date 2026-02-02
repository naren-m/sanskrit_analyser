"""Transliteration utilities for Sanskrit text."""

from sanskrit_analyzer.models.scripts import Script

# Mapping from our Script enum to indic_transliteration scheme names
_SCRIPT_TO_SCHEME = {
    Script.DEVANAGARI: "devanagari",
    Script.IAST: "iast",
    Script.SLP1: "slp1",
    Script.HK: "hk",
    Script.VELTHUIS: "velthuis",
    Script.ITRANS: "itrans",
}


def transliterate(text: str, from_script: Script, to_script: Script) -> str:
    """Transliterate Sanskrit text between scripts.

    Args:
        text: The text to transliterate.
        from_script: The source script of the input text.
        to_script: The target script for output.

    Returns:
        The transliterated text.

    Examples:
        >>> transliterate("राम", Script.DEVANAGARI, Script.IAST)
        'rāma'
        >>> transliterate("rāma", Script.IAST, Script.SLP1)
        'rAma'
    """
    if from_script == to_script:
        return text

    if not text.strip():
        return text

    from indic_transliteration import sanscript

    from_scheme = _SCRIPT_TO_SCHEME[from_script]
    to_scheme = _SCRIPT_TO_SCHEME[to_script]

    result: str = sanscript.transliterate(text, from_scheme, to_scheme)
    return result


def to_slp1(text: str, from_script: Script) -> str:
    """Convert text to SLP1 script.

    SLP1 is the preferred internal representation for processing.

    Args:
        text: The text to convert.
        from_script: The source script.

    Returns:
        Text in SLP1 script.
    """
    return transliterate(text, from_script, Script.SLP1)


def to_devanagari(text: str, from_script: Script) -> str:
    """Convert text to Devanagari script.

    Args:
        text: The text to convert.
        from_script: The source script.

    Returns:
        Text in Devanagari script.
    """
    return transliterate(text, from_script, Script.DEVANAGARI)


def to_iast(text: str, from_script: Script) -> str:
    """Convert text to IAST (International Alphabet of Sanskrit Transliteration).

    Args:
        text: The text to convert.
        from_script: The source script.

    Returns:
        Text in IAST script.
    """
    return transliterate(text, from_script, Script.IAST)
