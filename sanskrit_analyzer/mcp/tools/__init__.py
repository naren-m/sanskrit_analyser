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
from sanskrit_analyzer.mcp.tools.grammar import (
    explain_parse,
    get_pratyaya,
    identify_compound,
    resolve_ambiguity,
)

__all__ = [
    "analyze_sentence",
    "conjugate_verb",
    "explain_parse",
    "get_morphology",
    "get_pratyaya",
    "identify_compound",
    "list_gana",
    "lookup_dhatu",
    "resolve_ambiguity",
    "search_dhatu",
    "split_sandhi",
    "transliterate",
]
