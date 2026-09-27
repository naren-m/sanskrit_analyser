"""Grammar tools for MCP server.

Every answer comes from a real source: word analyses are re-derived through
vidyut-prakriya (``prakriya.analyze_pada``) so each reading carries its sūtra
trace, compound members come from the kosha-backed sandhi segmenter, and the
selected parse is whatever the shared ``Analyzer`` actually chose.
"""

import asyncio
from collections.abc import Awaitable, Callable
from typing import Any

from mcp.types import TextContent, Tool

from sanskrit_analyzer import Analyzer
from sanskrit_analyzer.config import Config
from sanskrit_analyzer.dhatu import segmenter
from sanskrit_analyzer.mcp.response import error_response, json_response, text_response
from sanskrit_analyzer.models.scripts import Script
from sanskrit_analyzer.prakriya.analyzer import PadaAnalysis, analyze_pada, pratyayas
from sanskrit_analyzer.prakriya.normalize import normalize
from sanskrit_analyzer.utils.transliterate import transliterate
from sanskrit_analyzer.vidyut_data import is_available as vidyut_available

ToolDispatcher = Callable[[str, dict[str, Any]], Awaitable[list[TextContent] | None]]

_NO_VIDYUT = "vidyut data bundle not found (set VIDYUT_DATA_DIR)"
# Readings per word. Common forms verify 10-30 ways (gataH: 14); the default
# of 5 would silently drop real readings.
_MAX_READINGS = 30


def _text_schema(key: str, description: str) -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {key: {"type": "string", "description": description}},
        "required": [key],
    }


def build_grammar_tools(
    analyzer: Analyzer | None = None,
) -> tuple[list[Tool], ToolDispatcher]:
    """Build the grammar tool specs and their dispatcher (see build_analysis_tools)."""
    analyzer = analyzer or Analyzer(Config.load())

    tools = [
        Tool(
            name="explain_parse",
            description=(
                "List every reading of each word that vidyut-prakriya can "
                "re-derive, with the sūtra-by-sūtra derivation"
            ),
            inputSchema=_text_schema("text", "Sanskrit text to analyze"),
        ),
        Tool(
            name="identify_compound",
            description=(
                "Split a compound (samāsa) into its members; the samāsa type "
                "is not classified"
            ),
            inputSchema=_text_schema("word", "Sanskrit compound word"),
        ),
        Tool(
            name="get_pratyaya",
            description=(
                "Identify the suffixes (pratyayas) in each derivable reading "
                "of a word, with the sūtra that adds each"
            ),
            inputSchema=_text_schema("word", "Sanskrit word to analyze"),
        ),
        Tool(
            name="resolve_ambiguity",
            description=(
                "Report the parse the analyzer selected and whether a "
                "disambiguation stage ran"
            ),
            inputSchema=_text_schema("text", "Sanskrit text to disambiguate"),
        ),
    ]

    async def dispatch(
        name: str, arguments: dict[str, Any]
    ) -> list[TextContent] | None:
        if name == "explain_parse":
            return await _explain_parse(arguments)
        elif name == "identify_compound":
            return await _identify_compound(arguments)
        elif name == "get_pratyaya":
            return await _get_pratyaya(arguments)
        elif name == "resolve_ambiguity":
            return await _resolve_ambiguity(analyzer, arguments)
        return None

    return tools, dispatch


def _derivable_readings(text: str) -> list[tuple[str, list[PadaAnalysis]]]:
    """(word, verified analyses) per normalized word. Blocking: run in a thread."""
    return [(w, analyze_pada(w, limit=_MAX_READINGS)) for w in normalize(text).words]


def _iast(slp1: str) -> str:
    return transliterate(slp1, Script.SLP1, Script.IAST)


async def _explain_parse(arguments: dict[str, Any]) -> list[TextContent]:
    """Handle explain_parse tool call."""
    text = arguments.get("text", "")
    if not text:
        return error_response("text parameter is required")
    if not vidyut_available():
        return error_response(_NO_VIDYUT)
    try:
        readings = await asyncio.to_thread(_derivable_readings, text)
        return json_response({
            "words": [
                {"surface": w, "analyses": [a.to_dict() for a in analyses]}
                for w, analyses in readings
            ],
        })
    except Exception as e:
        return error_response(f"explaining parse: {e}")


async def _identify_compound(arguments: dict[str, Any]) -> list[TextContent]:
    """Handle identify_compound tool call."""
    word = arguments.get("word", "")
    if not word:
        return error_response("word parameter is required")
    if not segmenter.is_available():
        return error_response(_NO_VIDYUT)

    def split() -> list[tuple[str, list[str]]]:
        return [(w, segmenter.segment_slp(w)) for w in normalize(word).words]

    try:
        compounds = [
            {
                "surface": w,
                "members_slp1": members,
                "members_iast": [_iast(m) for m in members],
                # Nothing in the library classifies samāsa type honestly.
                "compound_type": None,
            }
            for w, members in await asyncio.to_thread(split)
            if len(members) > 1
        ]
    except Exception as e:
        return error_response(f"identifying compound: {e}")
    if not compounds:
        return text_response(
            f"No split found for: {word} (not a compound, or listed whole in the kosha)"
        )
    return json_response(compounds)


async def _get_pratyaya(arguments: dict[str, Any]) -> list[TextContent]:
    """Handle get_pratyaya tool call."""
    word = arguments.get("word", "")
    if not word:
        return error_response("word parameter is required")
    if not vidyut_available():
        return error_response(_NO_VIDYUT)
    try:
        readings = await asyncio.to_thread(_derivable_readings, word)
    except Exception as e:
        return error_response(f"getting pratyayas: {e}")
    results = [
        {
            "surface": w,
            "lemma": a.lemma,
            "kind": a.kind,
            "morph": a.morph,
            "pratyayas": pratyayas(a.prakriya),
        }
        for w, analyses in readings
        for a in analyses
    ]
    if not results:
        return text_response(f"No derivable reading for: {word}")
    return json_response(results)


async def _resolve_ambiguity(
    analyzer: Analyzer, arguments: dict[str, Any]
) -> list[TextContent]:
    """Handle resolve_ambiguity tool call."""
    text = arguments.get("text", "")
    if not text:
        return error_response("text parameter is required")

    try:
        result = await analyzer.analyze(text)
    except Exception as e:
        return error_response(f"resolving ambiguity: {e}")

    selected = result.best_parse
    if selected is None:
        return text_response("No parses found")

    return json_response({
        "selected_parse_index": result.parse_forest.index(selected),
        "selected_parse_id": selected.parse_id,
        "confidence": selected.confidence,
        "total_candidates": len(result.parse_forest),
        "disambiguation_applied": result.confidence.disambiguation_applied,
        "disambiguation_stage": result.confidence.disambiguation_stage,
        "selected_breakdown": [
            {
                "form": w.surface_form,
                "lemma": w.lemma,
                "morphology": w.morphology.to_dict() if w.morphology else None,
            }
            for w in selected.all_words
        ],
        "all_candidates": [
            {
                "index": i,
                "confidence": parse.confidence,
                "word_count": len(parse.all_words),
            }
            for i, parse in enumerate(result.parse_forest)
        ],
    })
