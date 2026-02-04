"""Grammar tools for MCP server."""

from typing import Any

from sanskrit_analyzer.analyzer import Analyzer
from sanskrit_analyzer.config import AnalysisMode, Config

# Shared analyzer instance
_analyzer = Analyzer(Config())

# Verbosity levels
DEFAULT_VERBOSITY = "standard"
VERBOSITY_MINIMAL = "minimal"
VERBOSITY_DETAILED = "detailed"


def _normalize_verbosity(verbosity: str | None) -> str:
    """Normalize verbosity parameter to lowercase with default."""
    return (verbosity or DEFAULT_VERBOSITY).lower()


def _error_response(error: Exception) -> dict[str, Any]:
    """Create a standardized error response."""
    return {"success": False, "error": str(error)}


def _build_confidence_reasoning(overall: float, engine_agreement: float) -> str:
    """Build human-readable reasoning from confidence scores."""
    if overall > 0.9:
        base = "High confidence from ensemble agreement"
    elif overall > 0.7:
        base = "Moderate confidence"
    else:
        base = "Low confidence - multiple interpretations possible"

    if engine_agreement > 0.8:
        return f"{base}. Engines largely agree"
    return base


async def explain_parse(
    text: str,
    parse_indices: list[int] | None = None,
    verbosity: str | None = None,
) -> dict[str, Any]:
    """Compare multiple parse interpretations of Sanskrit text.

    Args:
        text: Sanskrit text to analyze.
        parse_indices: Optional list of parse indices to include (0-based).
                       If None, returns all parses.
        verbosity: Response detail level - 'minimal', 'standard', or 'detailed'.

    Returns:
        Dictionary with parse comparisons:
        - original_text: The input text
        - parse_count: Total number of parses found
        - parses: List of parse interpretations with confidence and words
    """
    verbosity = _normalize_verbosity(verbosity)

    try:
        result = await _analyzer.analyze(text, mode=AnalysisMode.ACADEMIC)
    except Exception as e:
        return _error_response(e)

    parses = result.parse_forest
    if not parses:
        return {
            "success": True,
            "original_text": text,
            "parse_count": 0,
            "parses": [],
        }

    # Filter to requested indices if provided
    if parse_indices:
        parses = [p for i, p in enumerate(parses) if i in parse_indices]

    formatted_parses = []
    for i, parse in enumerate(parses):
        parse_data: dict[str, Any] = {
            "index": i,
            "confidence": parse.confidence,
            "is_selected": getattr(parse, "is_selected", False),
        }

        if verbosity != VERBOSITY_MINIMAL:
            words = []
            for sg in parse.sandhi_groups:
                for bw in sg.base_words:
                    word_info: dict[str, Any] = {
                        "lemma": bw.lemma,
                        "surface_form": bw.surface_form,
                    }
                    if bw.morphology:
                        word_info["pos"] = getattr(bw.morphology, "pos", None)
                    words.append(word_info)
            parse_data["words"] = words

        if verbosity == VERBOSITY_DETAILED:
            # Include engine votes if available
            if hasattr(parse, "engine_votes"):
                parse_data["engine_votes"] = parse.engine_votes
            # Include sandhi group details
            parse_data["sandhi_groups"] = [
                {
                    "surface_form": sg.surface_form,
                    "sandhi_type": sg.sandhi_type.value if sg.sandhi_type else None,
                    "word_count": len(sg.base_words),
                }
                for sg in parse.sandhi_groups
            ]

        formatted_parses.append(parse_data)

    return {
        "success": True,
        "original_text": result.original_text,
        "parse_count": len(result.parse_forest),
        "returned_count": len(formatted_parses),
        "parses": formatted_parses,
    }


async def identify_compound(
    word: str,
    verbosity: str | None = None,
) -> dict[str, Any]:
    """Identify compound type (samasa) in a Sanskrit word.

    Args:
        word: Sanskrit word to analyze (Devanagari or IAST).
        verbosity: Response detail level - 'minimal', 'standard', or 'detailed'.

    Returns:
        Dictionary with compound analysis:
        - word: The input word
        - is_compound: Whether the word is a compound
        - compound_type: Type of compound (tatpurusha, dvandva, etc.)
        - components: List of component words
    """
    verbosity = _normalize_verbosity(verbosity)

    try:
        result = await _analyzer.analyze(word, mode=AnalysisMode.PRODUCTION)
    except Exception as e:
        return _error_response(e)

    best_parse = result.best_parse
    if not best_parse or not best_parse.sandhi_groups:
        return {
            "success": True,
            "word": word,
            "is_compound": False,
            "compound_type": None,
            "components": [],
        }

    # Look for compound information in sandhi groups
    sg = best_parse.sandhi_groups[0]  # First group for single word

    response: dict[str, Any] = {
        "success": True,
        "word": word,
        "is_compound": sg.is_compound,
        "compound_type": sg.compound_type.value if sg.compound_type else None,
        "components": [bw.lemma for bw in sg.base_words],
    }

    if verbosity != VERBOSITY_MINIMAL and sg.base_words:
        response["component_details"] = [
            {
                "lemma": bw.lemma,
                "meaning": bw.meanings[0] if bw.meanings else None,
            }
            for bw in sg.base_words
        ]

    if verbosity == VERBOSITY_DETAILED:
        response["scripts"] = {
            "devanagari": result.scripts.devanagari,
            "iast": result.scripts.iast,
        }

    return response


async def get_pratyaya(
    word: str,
    verbosity: str | None = None,
) -> dict[str, Any]:
    """Identify suffixes (pratyayas) applied to a Sanskrit word.

    Args:
        word: Sanskrit word to analyze (Devanagari or IAST).
        verbosity: Response detail level - 'minimal', 'standard', or 'detailed'.

    Returns:
        Dictionary with pratyaya analysis:
        - word: The input word
        - pratyayas: List of identified suffixes with type and function
    """
    verbosity = _normalize_verbosity(verbosity)

    try:
        result = await _analyzer.analyze(word, mode=AnalysisMode.EDUCATIONAL)
    except Exception as e:
        return _error_response(e)

    best_parse = result.best_parse
    if not best_parse:
        return {
            "success": True,
            "word": word,
            "pratyayas": [],
        }

    pratyayas = []
    for sg in best_parse.sandhi_groups:
        for bw in sg.base_words:
            if hasattr(bw, "pratyayas") and bw.pratyayas:
                for p in bw.pratyayas:
                    pratyaya_data: dict[str, Any] = {
                        "name": p.name if hasattr(p, "name") else str(p),
                    }
                    if verbosity != VERBOSITY_MINIMAL:
                        pratyaya_data["type"] = getattr(p, "type", None)
                        pratyaya_data["function"] = getattr(p, "function", None)
                    if verbosity == VERBOSITY_DETAILED:
                        pratyaya_data["sutra"] = getattr(p, "sutra", None)
                    pratyayas.append(pratyaya_data)

    # Also check morphology for suffix indicators
    if not pratyayas:
        for sg in best_parse.sandhi_groups:
            for bw in sg.base_words:
                if bw.morphology:
                    # Infer pratyaya type from morphology
                    morph = bw.morphology
                    if getattr(morph, "tense", None):
                        pratyayas.append({
                            "name": "tiṅ",
                            "type": "tin",
                            "function": "verb ending",
                        })
                    elif getattr(morph, "case", None):
                        pratyayas.append({
                            "name": "sup",
                            "type": "sup",
                            "function": "nominal ending",
                        })

    lemma = None
    if best_parse.sandhi_groups:
        first_group = best_parse.sandhi_groups[0]
        if first_group.base_words:
            lemma = first_group.base_words[0].lemma

    return {
        "success": True,
        "word": word,
        "lemma": lemma,
        "pratyayas": pratyayas,
    }


async def resolve_ambiguity(
    text: str,
    context: str | None = None,
) -> dict[str, Any]:
    """Resolve ambiguous parses and return the most likely interpretation.

    Args:
        text: Sanskrit text to analyze.
        context: Optional sentence context for better disambiguation.

    Returns:
        Dictionary with disambiguation result:
        - selected_parse: Index of the selected parse
        - confidence: Confidence in the selection
        - reasoning: Explanation for the selection
        - all_parses: Summary of all parse candidates
    """
    try:
        full_text = f"{context} {text}" if context else text
        result = await _analyzer.analyze(full_text, mode=AnalysisMode.ACADEMIC)
    except Exception as e:
        return _error_response(e)

    if not result.parse_forest:
        return {
            "success": True,
            "text": text,
            "selected_parse": None,
            "confidence": 0.0,
            "reasoning": "No valid parses found",
            "all_parses": [],
        }

    # Find the selected/best parse
    best_parse = result.best_parse
    selected_idx = 0
    for i, p in enumerate(result.parse_forest):
        if p == best_parse:
            selected_idx = i
            break

    reasoning = _build_confidence_reasoning(
        result.confidence.overall,
        result.confidence.engine_agreement,
    )

    return {
        "success": True,
        "text": text,
        "selected_parse": selected_idx,
        "confidence": result.confidence.overall,
        "reasoning": reasoning,
        "needs_human_review": getattr(result, "needs_human_review", False),
        "all_parses": [
            {
                "index": i,
                "confidence": p.confidence,
                "word_count": sum(len(sg.base_words) for sg in p.sandhi_groups),
            }
            for i, p in enumerate(result.parse_forest[:5])  # Limit to 5
        ],
    }
