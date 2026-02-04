"""Verbosity handling for MCP tools."""

from enum import Enum
from typing import Any


class Verbosity(Enum):
    """Verbosity levels for MCP tool responses."""

    MINIMAL = "minimal"
    STANDARD = "standard"
    DETAILED = "detailed"


def parse_verbosity(verbosity_str: str | None) -> Verbosity:
    """Parse verbosity string to enum.

    Args:
        verbosity_str: Verbosity level string (minimal, standard, detailed).

    Returns:
        Verbosity enum value. Defaults to STANDARD.
    """
    if not verbosity_str:
        return Verbosity.STANDARD

    try:
        return Verbosity(verbosity_str.lower())
    except ValueError:
        return Verbosity.STANDARD


def format_word_data(
    word_data: dict[str, Any], verbosity: Verbosity
) -> dict[str, Any]:
    """Format word data based on verbosity level.

    Args:
        word_data: Full word data dictionary.
        verbosity: Desired verbosity level.

    Returns:
        Filtered word data based on verbosity.
    """
    if verbosity == Verbosity.MINIMAL:
        return {
            "lemma": word_data.get("lemma"),
            "pos": word_data.get("morphology", {}).get("pos") if word_data.get("morphology") else None,
        }

    if verbosity == Verbosity.STANDARD:
        result: dict[str, Any] = {
            "lemma": word_data.get("lemma"),
            "surface_form": word_data.get("surface_form"),
            "morphology": word_data.get("morphology"),
            "meanings": word_data.get("meanings", [])[:3],
            "confidence": word_data.get("confidence"),
        }
        if word_data.get("dhatu"):
            result["dhatu"] = {
                "root": word_data["dhatu"].get("dhatu_iast"),
                "meaning": word_data["dhatu"].get("meaning_english"),
            }
        return result

    # DETAILED - return everything
    return word_data


def format_parse_data(
    parse_data: dict[str, Any], verbosity: Verbosity
) -> dict[str, Any]:
    """Format parse data based on verbosity level.

    Args:
        parse_data: Full parse data dictionary.
        verbosity: Desired verbosity level.

    Returns:
        Filtered parse data based on verbosity.
    """
    if verbosity == Verbosity.MINIMAL:
        return {
            "parse_id": parse_data.get("parse_id"),
            "confidence": parse_data.get("confidence"),
        }

    if verbosity == Verbosity.STANDARD:
        result: dict[str, Any] = {
            "parse_id": parse_data.get("parse_id"),
            "confidence": parse_data.get("confidence"),
            "sandhi_groups": [],
        }
        for sg in parse_data.get("sandhi_groups", []):
            sg_data: dict[str, Any] = {
                "surface_form": sg.get("surface_form"),
                "words": [format_word_data(w, verbosity) for w in sg.get("words", [])],
            }
            result["sandhi_groups"].append(sg_data)
        return result

    # DETAILED - return everything
    return parse_data


def format_dhatu_data(
    dhatu_data: dict[str, Any], verbosity: Verbosity
) -> dict[str, Any]:
    """Format dhatu data based on verbosity level.

    Args:
        dhatu_data: Full dhatu data dictionary.
        verbosity: Desired verbosity level.

    Returns:
        Filtered dhatu data based on verbosity.
    """
    if verbosity == Verbosity.MINIMAL:
        return {
            "dhatu_iast": dhatu_data.get("dhatu_iast"),
            "gana": dhatu_data.get("gana"),
            "meaning_english": dhatu_data.get("meaning_english"),
        }

    if verbosity == Verbosity.STANDARD:
        return {
            "id": dhatu_data.get("id"),
            "dhatu_devanagari": dhatu_data.get("dhatu_devanagari"),
            "dhatu_iast": dhatu_data.get("dhatu_iast"),
            "meaning_english": dhatu_data.get("meaning_english"),
            "gana": dhatu_data.get("gana"),
            "pada": dhatu_data.get("pada"),
        }

    # DETAILED - return everything
    return dhatu_data
