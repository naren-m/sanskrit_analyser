"""Analysis tools for MCP server."""

from typing import Any

from sanskrit_analyzer.analyzer import Analyzer
from sanskrit_analyzer.config import AnalysisMode, Config

# Map mode strings to AnalysisMode enum values
_MODE_MAP = {mode.value: mode for mode in AnalysisMode}


async def analyze_sentence(
    text: str,
    mode: str | None = None,
    verbosity: str | None = None,
) -> dict[str, Any]:
    """Analyze a Sanskrit sentence and return full morphological breakdown.

    Args:
        text: Sanskrit text to analyze (Devanagari, IAST, or SLP1).
        mode: Analysis mode - 'educational', 'production', or 'academic'.
              Defaults to 'production'.
        verbosity: Response detail level - 'minimal', 'standard', or 'detailed'.
                   Defaults to 'standard'.

    Returns:
        Dictionary with analysis results including:
        - sentence_id: Unique identifier for this analysis
        - original_text: The input text
        - scripts: Text in multiple scripts (devanagari, iast, slp1)
        - sandhi_groups: List of sandhi-joined units
        - words: List of base words with morphology
        - confidence: Overall confidence score
        - parse_count: Number of possible interpretations
    """
    analysis_mode = _MODE_MAP.get((mode or "").lower(), AnalysisMode.PRODUCTION)
    verbosity = (verbosity or "standard").lower()

    analyzer = Analyzer(Config())

    try:
        result = await analyzer.analyze(text, mode=analysis_mode)
    except Exception as e:
        return {"error": str(e), "success": False}

    return _format_analysis_response(result, verbosity)


def _format_analysis_response(tree: Any, verbosity: str) -> dict[str, Any]:
    """Format AnalysisTree as MCP response."""
    response: dict[str, Any] = {
        "success": True,
        "sentence_id": tree.sentence_id,
        "original_text": tree.original_text,
        "scripts": {
            "devanagari": tree.scripts.devanagari,
            "iast": tree.scripts.iast,
            "slp1": tree.scripts.slp1,
        },
        "confidence": tree.confidence.overall,
        "parse_count": len(tree.parse_forest),
    }

    # Get best parse
    best_parse = tree.best_parse
    if not best_parse:
        response["sandhi_groups"] = []
        response["words"] = []
        return response

    # Format sandhi groups and words
    sandhi_groups = []
    all_words = []

    for sg in best_parse.sandhi_groups:
        sg_data: dict[str, Any] = {"surface_form": sg.surface_form}

        if verbosity != "minimal":
            sg_data["word_count"] = len(sg.base_words)

        words_in_group = []
        for bw in sg.base_words:
            word_data = _format_word(bw, verbosity)
            words_in_group.append(word_data)
            all_words.append(word_data)

        if verbosity == "detailed":
            sg_data["words"] = words_in_group

        sandhi_groups.append(sg_data)

    response["sandhi_groups"] = sandhi_groups
    response["words"] = all_words

    # Add extra details for non-minimal verbosity
    if verbosity != "minimal":
        response["mode"] = tree.mode
        response["needs_human_review"] = getattr(tree, "needs_human_review", False)

    if verbosity == "detailed":
        response["engine_agreement"] = tree.confidence.engine_agreement
        if tree.confidence.disambiguation_score is not None:
            response["disambiguation_score"] = tree.confidence.disambiguation_score

    return response


_MORPH_FIELDS = ("pos", "gender", "number", "case", "person", "tense", "mood", "voice")


def _format_word(word: Any, verbosity: str) -> dict[str, Any]:
    """Format a BaseWord for the response."""
    data: dict[str, Any] = {
        "lemma": word.lemma,
        "surface_form": word.surface_form,
    }

    if verbosity == "minimal":
        if word.morphology:
            data["morph"] = _compact_morphology(word.morphology)
        return data

    # Standard and detailed: include meanings and full morphology
    data["meanings"] = [str(m) for m in word.meanings] if word.meanings else []
    data["confidence"] = word.confidence

    if word.morphology:
        data["morphology"] = {
            field: getattr(word.morphology, field, None) for field in _MORPH_FIELDS
        }

    if verbosity == "detailed":
        if word.dhatu:
            data["dhatu"] = {
                "root": word.dhatu.dhatu,
                "meaning": word.dhatu.meaning,
                "gana": word.dhatu.gana,
                "pada": word.dhatu.pada,
            }
        if word.scripts:
            data["scripts"] = {
                "devanagari": word.scripts.devanagari,
                "iast": word.scripts.iast,
                "slp1": word.scripts.slp1,
            }

    return data


def _compact_morphology(morph: Any) -> str:
    """Create compact morphology string like 'N.m.sg.nom'."""
    parts = []
    if pos := getattr(morph, "pos", None):
        parts.append(pos[0].upper())  # First letter
    if gender := getattr(morph, "gender", None):
        parts.append(gender[:1].lower())
    if number := getattr(morph, "number", None):
        parts.append(number[:2].lower())
    if case := getattr(morph, "case", None):
        parts.append(case[:3].lower())
    if person := getattr(morph, "person", None):
        parts.append(f"p{person}")
    if tense := getattr(morph, "tense", None):
        parts.append(tense[:3].lower())
    return ".".join(parts) if parts else ""
