"""Dhatu tools for MCP server."""

from typing import Any

from sanskrit_analyzer.data.dhatu_db import DhatuDB, DhatuEntry
from sanskrit_analyzer.mcp.verbosity import Verbosity, error_response, parse_verbosity

# Shared database instance
_db = DhatuDB()

# Traditional gana (verb class) names
GANA_NAMES = {
    1: "bhvādi",
    2: "adādi",
    3: "juhotyādi",
    4: "divādi",
    5: "svādi",
    6: "tudādi",
    7: "rudhādi",
    8: "tanādi",
    9: "kryādi",
    10: "curādi",
}


def _format_dhatu_entry(entry: DhatuEntry, level: Verbosity) -> dict[str, Any]:
    """Format a DhatuEntry for MCP response."""
    data: dict[str, Any] = {
        "dhatu": entry.dhatu_devanagari,
        "dhatu_iast": entry.dhatu_iast,
        "meaning": entry.meaning_english,
        "gana": entry.gana,
        "pada": entry.pada,
    }

    if level != Verbosity.MINIMAL:
        data["meaning_hindi"] = entry.meaning_hindi
        data["examples"] = entry.examples
        data["panini_reference"] = entry.panini_reference

    if level == Verbosity.DETAILED:
        data["it_category"] = entry.it_category
        data["synonyms"] = entry.synonyms
        data["related_words"] = entry.related_words
        data["id"] = entry.id

    return data


def lookup_dhatu(
    dhatu: str,
    include_conjugations: bool = False,
    verbosity: str | None = None,
) -> dict[str, Any]:
    """Look up a dhatu by its root form.

    Args:
        dhatu: The verbal root (Devanagari or IAST).
        include_conjugations: Whether to include conjugation tables.
        verbosity: Response detail level - 'minimal', 'standard', or 'detailed'.

    Returns:
        Dictionary with dhatu information:
        - dhatu: The root in Devanagari
        - meaning: English meaning
        - gana: Verb class (1-10)
        - pada: Voice type
        - conjugations: Optional conjugation forms
    """
    level = parse_verbosity(verbosity)

    try:
        entry = _db.lookup_by_dhatu(dhatu, include_conjugations=include_conjugations)
    except Exception as e:
        return error_response(e)

    if not entry:
        return error_response(f"Dhatu not found: {dhatu}")

    result = _format_dhatu_entry(entry, level)
    result["success"] = True

    if include_conjugations and entry.conjugations:
        result["conjugations"] = [
            {
                "lakara": c.lakara,
                "purusha": c.purusha,
                "vacana": c.vacana,
                "pada": c.pada,
                "form": c.form_devanagari,
                "form_iast": c.form_iast,
            }
            for c in entry.conjugations
        ]

    return result


def search_dhatu(
    query: str,
    limit: int = 10,
    verbosity: str | None = None,
) -> dict[str, Any]:
    """Search dhatus by meaning or pattern.

    Args:
        query: Search query (matches dhatu form, meaning, examples).
        limit: Maximum number of results (default 10).
        verbosity: Response detail level - 'minimal', 'standard', or 'detailed'.

    Returns:
        Dictionary with search results:
        - results: List of matching dhatu entries
        - count: Number of results
    """
    level = parse_verbosity(verbosity)
    limit = min(max(1, limit), 50)  # Clamp to 1-50

    try:
        entries = _db.search(query, limit=limit)
    except Exception as e:
        return error_response(e)

    return {
        "success": True,
        "query": query,
        "count": len(entries),
        "results": [_format_dhatu_entry(e, level) for e in entries],
    }


def conjugate_verb(
    dhatu: str,
    lakara: str | None = None,
    purusha: str | None = None,
    vacana: str | None = None,
) -> dict[str, Any]:
    """Get conjugation forms for a dhatu.

    Args:
        dhatu: The verbal root (Devanagari or IAST).
        lakara: Optional tense/mood filter (lat, lit, lut, lrt, let, lot, lan, etc.).
        purusha: Optional person filter (prathama, madhyama, uttama).
        vacana: Optional number filter (ekavacana, dvivacana, bahuvacana).

    Returns:
        Dictionary with conjugation forms:
        - dhatu: The root
        - forms: List of conjugation forms matching filters
    """
    try:
        entry = _db.lookup_by_dhatu(dhatu, include_conjugations=False)
    except Exception as e:
        return error_response(e)

    if not entry:
        return error_response(f"Dhatu not found: {dhatu}")

    try:
        forms = _db.get_conjugation(
            entry.id,
            lakara=lakara or "lat",  # Default to present tense
            purusha=purusha,
            vacana=vacana,
        )
    except Exception as e:
        return error_response(e)

    return {
        "success": True,
        "dhatu": entry.dhatu_devanagari,
        "dhatu_iast": entry.dhatu_iast,
        "gana": entry.gana,
        "pada": entry.pada,
        "lakara": lakara or "lat",
        "form_count": len(forms),
        "forms": [
            {
                "purusha": f.purusha,
                "vacana": f.vacana,
                "pada": f.pada,
                "form": f.form_devanagari,
                "form_iast": f.form_iast,
            }
            for f in forms
        ],
    }


def list_gana(
    gana: int,
    limit: int = 20,
) -> dict[str, Any]:
    """List dhatus belonging to a specific verb class (gana).

    Args:
        gana: Verb class number (1-10).
        limit: Maximum number of results (default 20).

    Returns:
        Dictionary with gana dhatus:
        - gana: The verb class number
        - gana_name: Traditional name of the gana
        - count: Number of results
        - dhatus: List of dhatu entries
    """
    if gana < 1 or gana > 10:
        return error_response(f"Invalid gana: {gana}. Must be 1-10.")

    limit = min(max(1, limit), 100)  # Clamp to 1-100

    try:
        entries = _db.get_by_gana(gana, limit=limit)
    except Exception as e:
        return error_response(e)

    return {
        "success": True,
        "gana": gana,
        "gana_name": GANA_NAMES.get(gana, ""),
        "count": len(entries),
        "dhatus": [
            {
                "dhatu": e.dhatu_devanagari,
                "dhatu_iast": e.dhatu_iast,
                "meaning": e.meaning_english,
                "pada": e.pada,
            }
            for e in entries
        ],
    }
