"""Verbosity handling for MCP tools.

Provides consistent verbosity levels across all MCP tools:
- minimal: Essential data only (lemma, morphology codes)
- standard: Data with common fields expanded (default)
- detailed: Full data with explanatory text
"""

from enum import Enum
from typing import Any


class Verbosity(Enum):
    """Response detail level for MCP tools."""

    MINIMAL = "minimal"
    STANDARD = "standard"
    DETAILED = "detailed"


def parse_verbosity(value: str | None) -> Verbosity:
    """Parse verbosity string to enum, defaulting to STANDARD.

    Args:
        value: Verbosity string (minimal, standard, detailed) or None.

    Returns:
        Verbosity enum value.
    """
    if not value:
        return Verbosity.STANDARD
    normalized = value.lower().strip()
    try:
        return Verbosity(normalized)
    except ValueError:
        return Verbosity.STANDARD


def error_response(error: Exception | str) -> dict[str, Any]:
    """Create a standardized error response.

    Args:
        error: Exception or error message string.

    Returns:
        Dictionary with success=False and error message.
    """
    return {"success": False, "error": str(error)}
