"""Analysis tools for MCP server."""

from typing import Any

from mcp.server import Server
from mcp.types import Tool, TextContent

from sanskrit_analyzer import Analyzer
from sanskrit_analyzer.config import Config
from sanskrit_analyzer.mcp.response import error_response, json_response, text_response
from sanskrit_analyzer.utils.normalize import detect_script
from sanskrit_analyzer.utils.transliterate import transliterate, Script


def register_analysis_tools(server: Server) -> None:
    """Register analysis tools with the MCP server.

    Args:
        server: MCP server instance.
    """
    analyzer = Analyzer(Config())

    @server.list_tools()
    async def list_tools() -> list[Tool]:
        return [
            Tool(
                name="analyze_sentence",
                description="Analyze a Sanskrit sentence and get full morphological breakdown",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "text": {
                            "type": "string",
                            "description": "Sanskrit text to analyze (any script)",
                        },
                    },
                    "required": ["text"],
                },
            ),
            Tool(
                name="split_sandhi",
                description="Split sandhi in Sanskrit text to show word boundaries",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "text": {
                            "type": "string",
                            "description": "Sanskrit text to split",
                        },
                    },
                    "required": ["text"],
                },
            ),
            Tool(
                name="get_morphology",
                description="Get morphological tags for a Sanskrit word",
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
                name="transliterate",
                description="Convert Sanskrit text between scripts",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "text": {
                            "type": "string",
                            "description": "Text to convert",
                        },
                        "to_script": {
                            "type": "string",
                            "enum": ["devanagari", "iast", "slp1", "itrans"],
                            "description": "Target script",
                        },
                    },
                    "required": ["text", "to_script"],
                },
            ),
        ]

    @server.call_tool()
    async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
        if name == "analyze_sentence":
            return await _analyze_sentence(analyzer, arguments)
        elif name == "split_sandhi":
            return await _split_sandhi(analyzer, arguments)
        elif name == "get_morphology":
            return await _get_morphology(analyzer, arguments)
        elif name == "transliterate":
            return _transliterate(arguments)
        else:
            return error_response(f"Unknown tool: {name}")


async def _analyze_sentence(
    analyzer: Analyzer, arguments: dict[str, Any]
) -> list[TextContent]:
    """Handle analyze_sentence tool call."""
    text = arguments.get("text", "")

    if not text:
        return error_response("text parameter is required")

    try:
        result = await analyzer.analyze(text)

        output: dict[str, Any] = {
            "sentence": {
                "original": result.original_text,
                "normalized": result.normalized_slp1,
            },
            "confidence": result.confidence.overall,
            "parses": [],
        }

        for parse in result.parse_forest:
            parse_data: dict[str, Any] = {
                "parse_id": parse.parse_id,
                "confidence": parse.confidence,
                "sandhi_groups": [],
            }

            for sg in parse.sandhi_groups:
                sg_data: dict[str, Any] = {
                    "surface_form": sg.surface_form,
                    "words": [],
                }

                for word in sg.base_words:
                    word_data: dict[str, Any] = {
                        "lemma": word.lemma,
                        "surface_form": word.surface_form,
                        "morphology": word.morphology.to_dict() if word.morphology else None,
                        "meanings": [str(m) for m in word.meanings],
                        "confidence": word.confidence,
                    }
                    if word.dhatu:
                        word_data["dhatu"] = word.dhatu.to_dict()
                    sg_data["words"].append(word_data)

                parse_data["sandhi_groups"].append(sg_data)

            output["parses"].append(parse_data)

        return json_response(output)

    except Exception as e:
        return error_response(f"analyzing text: {e}")


async def _split_sandhi(
    analyzer: Analyzer, arguments: dict[str, Any]
) -> list[TextContent]:
    """Handle split_sandhi tool call."""
    text = arguments.get("text", "")

    if not text:
        return error_response("text parameter is required")

    try:
        result = await analyzer.analyze(text)

        if not result.parse_forest:
            return text_response("No parse found")

        best_parse = result.parse_forest[0]
        splits: list[dict[str, Any]] = []

        for sg in best_parse.sandhi_groups:
            split_data: dict[str, Any] = {
                "original": sg.surface_form,
                "components": [w.lemma for w in sg.base_words],
            }
            if sg.sandhi_type:
                split_data["sandhi_type"] = sg.sandhi_type.value
            if sg.sandhi_rule:
                split_data["rule"] = sg.sandhi_rule
            splits.append(split_data)

        return json_response(splits)

    except Exception as e:
        return error_response(f"splitting sandhi: {e}")


async def _get_morphology(
    analyzer: Analyzer, arguments: dict[str, Any]
) -> list[TextContent]:
    """Handle get_morphology tool call."""
    word = arguments.get("word", "")

    if not word:
        return error_response("word parameter is required")

    try:
        result = await analyzer.analyze(word)

        if not result.parse_forest:
            return text_response("No parse found")

        best_parse = result.parse_forest[0]
        morphologies: list[dict[str, Any]] = []

        for sg in best_parse.sandhi_groups:
            for w in sg.base_words:
                morph_data: dict[str, Any] = {
                    "lemma": w.lemma,
                    "surface_form": w.surface_form,
                }
                if w.morphology:
                    morph_data["morphology"] = w.morphology.to_dict()
                morphologies.append(morph_data)

        return json_response(morphologies)

    except Exception as e:
        return error_response(f"getting morphology: {e}")


_SCRIPT_MAP = {
    "devanagari": Script.DEVANAGARI,
    "iast": Script.IAST,
    "slp1": Script.SLP1,
    "itrans": Script.ITRANS,
}


def _transliterate(arguments: dict[str, Any]) -> list[TextContent]:
    """Handle transliterate tool call."""
    text = arguments.get("text", "")
    to_script_str = arguments.get("to_script", "")

    if not text:
        return error_response("text parameter is required")

    if not to_script_str:
        return error_response("to_script parameter is required")

    try:
        to_script = _SCRIPT_MAP.get(to_script_str.lower())
        if not to_script:
            return error_response(f"Unknown script: {to_script_str}")

        from_script = detect_script(text)
        result = transliterate(text, from_script, to_script)
        return text_response(result)

    except Exception as e:
        return error_response(f"transliterating: {e}")
