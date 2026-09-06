"""Dhatu tools for MCP server."""

from collections.abc import Awaitable, Callable
from typing import Any

from mcp.types import TextContent, Tool

from sanskrit_analyzer.dhatu import conjugation
from sanskrit_analyzer.dhatu.dhatupatha import DhatuKosha, entry_to_dict, get_dhatu_kosha
from sanskrit_analyzer.mcp.response import error_response, json_response, text_response

ToolDispatcher = Callable[[str, dict[str, Any]], Awaitable[list[TextContent] | None]]


def build_dhatu_tools() -> tuple[list[Tool], ToolDispatcher]:
    """Build the dhatu tool specs and their dispatcher (see build_analysis_tools)."""
    kosha = get_dhatu_kosha()

    tools = [
            Tool(
                name="lookup_dhatu",
                description=(
                    "Look up a dhatu (verbal root) in the Dhatupatha. Accepts "
                    "Devanagari, IAST, SLP1, or the citation form (qukfY)."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "dhatu": {
                            "type": "string",
                            "description": "Dhatu root (e.g., gam, bhu, kf)",
                        },
                    },
                    "required": ["dhatu"],
                },
            ),
            Tool(
                name="search_dhatu",
                description="Search dhatus by root form or artha (the Sanskrit gloss)",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Search query (root form or artha)",
                        },
                        "limit": {
                            "type": "integer",
                            "description": "Maximum results to return",
                            "default": 10,
                        },
                    },
                    "required": ["query"],
                },
            ),
            Tool(
                name="conjugate_verb",
                description=(
                    "Derive the conjugation table for a dhatu in one lakara "
                    "with the Paninian engine (needs the vidyut data bundle)."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "dhatu": {
                            "type": "string",
                            "description": "Dhatu root",
                        },
                        "lakara": {
                            "type": "string",
                            "description": (
                                "Tense/mood: lat, lit, lut, lrt, let, lot, lan, "
                                "vidhilin, ashirlin, lun, lrn"
                            ),
                            "default": "lat",
                        },
                    },
                    "required": ["dhatu"],
                },
            ),
            Tool(
                name="list_gana",
                description="List dhatus by verb class (gana)",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "gana": {
                            "type": "integer",
                            "description": "Gana number (1-10)",
                            "minimum": 1,
                            "maximum": 10,
                        },
                        "limit": {
                            "type": "integer",
                            "description": "Maximum results to return",
                            "default": 20,
                        },
                    },
                    "required": ["gana"],
                },
            ),
        ]

    async def dispatch(
        name: str, arguments: dict[str, Any]
    ) -> list[TextContent] | None:
        if name == "lookup_dhatu":
            return _lookup_dhatu(kosha, arguments)
        elif name == "search_dhatu":
            return _search_dhatu(kosha, arguments)
        elif name == "conjugate_verb":
            return _conjugate_verb(kosha, arguments)
        elif name == "list_gana":
            return _list_gana(kosha, arguments)
        return None

    return tools, dispatch


def _lookup_dhatu(kosha: DhatuKosha, arguments: dict[str, Any]) -> list[TextContent]:
    """Handle lookup_dhatu tool call."""
    dhatu = arguments.get("dhatu", "")

    if not dhatu:
        return error_response("dhatu parameter is required")

    try:
        entries = kosha.find(dhatu)

        if not entries:
            return text_response(f"Dhatu not found: {dhatu}")

        # A root can hold several Dhatupatha entries: kf is in gana 5 and 8.
        return json_response([entry_to_dict(e) for e in entries])

    except Exception as e:
        return error_response(f"looking up dhatu: {e}")


def _clamp_limit(value: Any, default: int, maximum: int = 100) -> int:
    """Coerce a client-supplied ``limit`` to an int in ``[1, maximum]``.

    The low-level MCP server does not enforce the JSON-schema ``minimum``/
    ``maximum``, so arguments arrive unvalidated (and possibly non-numeric).
    """
    try:
        limit = int(value)
    except (TypeError, ValueError):
        return default
    return max(1, min(limit, maximum))


def _search_dhatu(kosha: DhatuKosha, arguments: dict[str, Any]) -> list[TextContent]:
    """Handle search_dhatu tool call."""
    query = arguments.get("query", "")
    limit = _clamp_limit(arguments.get("limit", 10), default=10)

    if not query:
        return error_response("query parameter is required")

    try:
        results = kosha.search(query, limit=limit)

        if not results:
            return text_response(f"No dhatus found matching: {query}")

        return json_response([entry_to_dict(entry) for entry in results])

    except Exception as e:
        return error_response(f"searching dhatus: {e}")


def _conjugate_verb(kosha: DhatuKosha, arguments: dict[str, Any]) -> list[TextContent]:
    """Handle conjugate_verb tool call."""
    dhatu = arguments.get("dhatu", "")
    lakara = arguments.get("lakara", "lat")

    if not dhatu:
        return error_response("dhatu parameter is required")
    if conjugation.normalize_lakara(lakara) is None:
        return error_response(
            f"unknown lakara: {lakara}. One of: {', '.join(conjugation.LAKARA_NAMES)}"
        )
    if not conjugation.is_available():
        return error_response(
            "conjugation needs the vidyut data bundle, which is not installed"
        )

    try:
        entries = kosha.find(dhatu)
        if not entries:
            return text_response(f"Dhatu not found: {dhatu}")

        return json_response(
            [
                {
                    **entry_to_dict(entry),
                    "padas": sorted({r["pada"] for r in rows}),
                    "forms": rows,
                }
                for entry in entries
                if (rows := conjugation.conjugate(entry["code"], lakara))
            ]
        )

    except Exception as e:
        return error_response(f"conjugating verb: {e}")


def _list_gana(kosha: DhatuKosha, arguments: dict[str, Any]) -> list[TextContent]:
    """Handle list_gana tool call."""
    gana = arguments.get("gana")
    limit = _clamp_limit(arguments.get("limit", 20), default=20)

    if gana is None:
        return error_response("gana parameter is required")

    # The low-level MCP server does not coerce/validate against the tool schema,
    # so gana may arrive as a non-int (e.g. the string "3"); coerce before compare.
    try:
        gana = int(gana)
    except (TypeError, ValueError):
        return error_response("gana must be an integer between 1 and 10")

    if not 1 <= gana <= 10:
        return error_response("gana must be between 1 and 10")

    try:
        results = kosha.by_gana(gana)[:limit]

        if not results:
            return text_response(f"No dhatus found in gana {gana}")

        return json_response([entry_to_dict(entry) for entry in results])

    except Exception as e:
        return error_response(f"listing gana: {e}")
