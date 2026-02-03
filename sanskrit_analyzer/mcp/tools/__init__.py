"""MCP tools for Sanskrit analysis, dhatu lookup, and grammar operations."""

from sanskrit_analyzer.mcp.tools.analysis import (
    analyze_sentence,
    get_morphology,
    split_sandhi,
    transliterate,
)
from sanskrit_analyzer.mcp.tools.dhatu import (
    conjugate_verb,
    list_gana,
    lookup_dhatu,
    search_dhatu,
)

__all__ = [
    "analyze_sentence",
    "conjugate_verb",
    "get_morphology",
    "list_gana",
    "lookup_dhatu",
    "search_dhatu",
    "split_sandhi",
    "transliterate",
]
