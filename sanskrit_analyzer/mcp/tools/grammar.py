"""Grammar tools for MCP server."""

from typing import Any

from mcp.server import Server
from mcp.types import Tool, TextContent

from sanskrit_analyzer import Analyzer
from sanskrit_analyzer.config import Config
from sanskrit_analyzer.mcp.response import error_response, json_response, text_response


def register_grammar_tools(server: Server) -> None:
    """Register grammar tools with the MCP server.

    Args:
        server: MCP server instance.
    """
    analyzer = Analyzer(Config())

    @server.list_tools()
    async def list_tools() -> list[Tool]:
        return [
            Tool(
                name="explain_parse",
                description="Compare multiple parse interpretations of ambiguous text",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "text": {
                            "type": "string",
                            "description": "Sanskrit text to analyze",
                        },
                    },
                    "required": ["text"],
                },
            ),
            Tool(
                name="identify_compound",
                description="Identify compound type (samasa) in a Sanskrit word",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "word": {
                            "type": "string",
                            "description": "Sanskrit compound word",
                        },
                    },
                    "required": ["word"],
                },
            ),
            Tool(
                name="get_pratyaya",
                description="Identify suffixes (pratyayas) applied to a word",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "word": {
                            "type": "string",
                            "description": "Sanskrit word to analyze",
                        },
                    },
                    "required": ["word"],
                },
            ),
            Tool(
                name="resolve_ambiguity",
                description="Resolve ambiguous parses to find the most likely interpretation",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "text": {
                            "type": "string",
                            "description": "Sanskrit text to disambiguate",
                        },
                    },
                    "required": ["text"],
                },
            ),
        ]

    @server.call_tool()
    async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
        if name == "explain_parse":
            return await _explain_parse(analyzer, arguments)
        elif name == "identify_compound":
            return await _identify_compound(analyzer, arguments)
        elif name == "get_pratyaya":
            return await _get_pratyaya(analyzer, arguments)
        elif name == "resolve_ambiguity":
            return await _resolve_ambiguity(analyzer, arguments)
        else:
            return [TextContent(type="text", text=f"Unknown tool: {name}")]


async def _explain_parse(
    analyzer: Analyzer, arguments: dict[str, Any]
) -> list[TextContent]:
    """Handle explain_parse tool call."""
    text = arguments.get("text", "")

    if not text:
        return error_response("text parameter is required")

    try:
        result = await analyzer.analyze(text)

        if not result.parse_forest:
            return text_response("No parses found")

        output: dict[str, Any] = {
            "total_parses": len(result.parse_forest),
            "parses": [],
        }

        for i, parse in enumerate(result.parse_forest):
            parse_data: dict[str, Any] = {
                "index": i,
                "parse_id": parse.parse_id,
                "confidence": parse.confidence,
                "breakdown": [],
            }

            for sg in parse.sandhi_groups:
                for word in sg.base_words:
                    word_info: dict[str, Any] = {
                        "form": word.surface_form,
                        "lemma": word.lemma,
                    }
                    if word.morphology:
                        word_info["analysis"] = word.morphology.to_dict()
                    parse_data["breakdown"].append(word_info)

            output["parses"].append(parse_data)

        return json_response(output)

    except Exception as e:
        return error_response(f"explaining parse: {e}")


async def _identify_compound(
    analyzer: Analyzer, arguments: dict[str, Any]
) -> list[TextContent]:
    """Handle identify_compound tool call."""
    word = arguments.get("word", "")

    if not word:
        return error_response("word parameter is required")

    try:
        result = await analyzer.analyze(word)

        if not result.parse_forest:
            return text_response("No parse found")

        best_parse = result.parse_forest[0]
        compounds: list[dict[str, Any]] = []

        for sg in best_parse.sandhi_groups:
            if sg.is_compound:
                compounds.append({
                    "surface_form": sg.surface_form,
                    "compound_type": sg.compound_type.value if sg.compound_type else "unknown",
                    "components": [w.lemma for w in sg.base_words],
                })

        if not compounds:
            return text_response(f"No compound detected in: {word}")

        return json_response(compounds)

    except Exception as e:
        return error_response(f"identifying compound: {e}")


async def _get_pratyaya(
    analyzer: Analyzer, arguments: dict[str, Any]
) -> list[TextContent]:
    """Handle get_pratyaya tool call."""
    word = arguments.get("word", "")

    if not word:
        return error_response("word parameter is required")

    try:
        result = await analyzer.analyze(word)

        if not result.parse_forest:
            return text_response("No parse found")

        best_parse = result.parse_forest[0]
        pratyayas: list[dict[str, Any]] = []

        for sg in best_parse.sandhi_groups:
            for w in sg.base_words:
                if w.pratyaya:
                    for p in w.pratyaya:
                        pratyayas.append({
                            "word": w.lemma,
                            "pratyaya": str(p),
                        })

        if not pratyayas:
            return text_response(f"No pratyayas identified in: {word}")

        return json_response(pratyayas)

    except Exception as e:
        return error_response(f"getting pratyayas: {e}")


async def _resolve_ambiguity(
    analyzer: Analyzer, arguments: dict[str, Any]
) -> list[TextContent]:
    """Handle resolve_ambiguity tool call."""
    text = arguments.get("text", "")

    if not text:
        return error_response("text parameter is required")

    try:
        result = await analyzer.analyze(text)

        if not result.parse_forest:
            return text_response("No parses found")

        selected = result.parse_forest[0]

        output: dict[str, Any] = {
            "selected_parse_index": 0,
            "selected_parse_id": selected.parse_id,
            "confidence": selected.confidence,
            "total_candidates": len(result.parse_forest),
            "reasoning": f"Selected based on confidence score {selected.confidence:.2%}",
            "selected_breakdown": [
                {
                    "form": w.surface_form,
                    "lemma": w.lemma,
                    "pos": w.morphology.pos if w.morphology else None,
                }
                for sg in selected.sandhi_groups
                for w in sg.base_words
            ],
            "all_candidates": [
                {
                    "index": i,
                    "confidence": parse.confidence,
                    "word_count": sum(len(sg.base_words) for sg in parse.sandhi_groups),
                }
                for i, parse in enumerate(result.parse_forest)
            ],
        }

        return json_response(output)

    except Exception as e:
        return error_response(f"resolving ambiguity: {e}")
