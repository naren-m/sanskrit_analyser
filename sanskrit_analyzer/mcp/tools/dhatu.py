"""Dhatu tools for MCP server."""

from typing import Any

from mcp.server import Server
from mcp.types import Tool, TextContent

from sanskrit_analyzer.data.dhatu_db import DhatuDB, DhatuEntry
from sanskrit_analyzer.mcp.response import error_response, json_response, text_response


def _dhatu_to_dict(entry: DhatuEntry) -> dict[str, Any]:
    """Convert DhatuEntry to dictionary."""
    return {
        "id": entry.id,
        "dhatu_devanagari": entry.dhatu_devanagari,
        "dhatu_iast": entry.dhatu_iast,
        "meaning_english": entry.meaning_english,
        "meaning_hindi": entry.meaning_hindi,
        "gana": entry.gana,
        "pada": entry.pada,
        "panini_reference": entry.panini_reference,
    }


def register_dhatu_tools(server: Server) -> None:
    """Register dhatu tools with the MCP server.

    Args:
        server: MCP server instance.
    """
    db = DhatuDB()

    @server.list_tools()
    async def list_tools() -> list[Tool]:
        return [
            Tool(
                name="lookup_dhatu",
                description="Look up a dhatu (verbal root) by its root form",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "dhatu": {
                            "type": "string",
                            "description": "Dhatu root (e.g., gam, bhU, kR)",
                        },
                    },
                    "required": ["dhatu"],
                },
            ),
            Tool(
                name="search_dhatu",
                description="Search dhatus by meaning or pattern",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Search query (meaning or root pattern)",
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
                description="Get conjugation forms for a dhatu",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "dhatu": {
                            "type": "string",
                            "description": "Dhatu root",
                        },
                        "lakara": {
                            "type": "string",
                            "description": "Tense/mood (lat, lit, lut, etc.)",
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

    @server.call_tool()
    async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
        if name == "lookup_dhatu":
            return _lookup_dhatu(db, arguments)
        elif name == "search_dhatu":
            return _search_dhatu(db, arguments)
        elif name == "conjugate_verb":
            return _conjugate_verb(db, arguments)
        elif name == "list_gana":
            return _list_gana(db, arguments)
        else:
            return error_response(f"Unknown tool: {name}")


def _lookup_dhatu(db: DhatuDB, arguments: dict[str, Any]) -> list[TextContent]:
    """Handle lookup_dhatu tool call."""
    dhatu = arguments.get("dhatu", "")

    if not dhatu:
        return error_response("dhatu parameter is required")

    try:
        entry = db.lookup_by_dhatu(dhatu)

        if not entry:
            return text_response(f"Dhatu not found: {dhatu}")

        return json_response(_dhatu_to_dict(entry))

    except Exception as e:
        return error_response(f"looking up dhatu: {e}")


def _search_dhatu(db: DhatuDB, arguments: dict[str, Any]) -> list[TextContent]:
    """Handle search_dhatu tool call."""
    query = arguments.get("query", "")
    limit = arguments.get("limit", 10)

    if not query:
        return error_response("query parameter is required")

    try:
        results = db.search(query, limit=limit)

        if not results:
            return text_response(f"No dhatus found matching: {query}")

        return json_response([_dhatu_to_dict(entry) for entry in results])

    except Exception as e:
        return error_response(f"searching dhatus: {e}")


def _conjugate_verb(db: DhatuDB, arguments: dict[str, Any]) -> list[TextContent]:
    """Handle conjugate_verb tool call."""
    dhatu = arguments.get("dhatu", "")
    lakara = arguments.get("lakara", "lat")

    if not dhatu:
        return error_response("dhatu parameter is required")

    try:
        conjugations = db.get_conjugation(dhatu, lakara)

        if not conjugations:
            return text_response(f"No conjugations found for: {dhatu}")

        result = [
            {
                "purusha": conj.purusha,
                "vacana": conj.vacana,
                "pada": conj.pada,
                "form_devanagari": conj.form_devanagari,
                "form_iast": conj.form_iast,
            }
            for conj in conjugations
        ]

        return json_response(result)

    except Exception as e:
        return error_response(f"conjugating verb: {e}")


def _list_gana(db: DhatuDB, arguments: dict[str, Any]) -> list[TextContent]:
    """Handle list_gana tool call."""
    gana = arguments.get("gana")
    limit = arguments.get("limit", 20)

    if gana is None:
        return error_response("gana parameter is required")

    if not 1 <= gana <= 10:
        return error_response("gana must be between 1 and 10")

    try:
        results = db.get_by_gana(gana, limit=limit)

        if not results:
            return text_response(f"No dhatus found in gana {gana}")

        return json_response([_dhatu_to_dict(entry) for entry in results])

    except Exception as e:
        return error_response(f"listing gana: {e}")
