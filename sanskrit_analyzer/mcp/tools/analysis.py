"""Analysis tools for MCP server."""

from typing import Any

from sanskrit_analyzer.analyzer import Analyzer
from sanskrit_analyzer.config import AnalysisMode, Config

# Map mode strings to AnalysisMode enum values
_MODE_MAP = {mode.value: mode for mode in AnalysisMode}

# Shared analyzer instance
_analyzer = Analyzer(Config())


async def _run_analysis(text: str, mode: AnalysisMode) -> dict[str, Any] | Any:
    """Run analysis and return result or error dict."""
    try:
        return await _analyzer.analyze(text, mode=mode)
    except Exception as e:
        return {"error": str(e), "success": False}


def _scripts_dict(scripts: Any) -> dict[str, str]:
    """Extract scripts as a dictionary."""
    return {
        "devanagari": scripts.devanagari,
        "iast": scripts.iast,
        "slp1": scripts.slp1,
    }


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

    result = await _run_analysis(text, analysis_mode)
    if isinstance(result, dict):
        return result

    return _format_analysis_response(result, verbosity)


def _format_analysis_response(tree: Any, verbosity: str) -> dict[str, Any]:
    """Format AnalysisTree as MCP response."""
    response: dict[str, Any] = {
        "success": True,
        "sentence_id": tree.sentence_id,
        "original_text": tree.original_text,
        "scripts": _scripts_dict(tree.scripts),
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
            data["scripts"] = _scripts_dict(word.scripts)

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


async def split_sandhi(
    text: str,
    verbosity: str | None = None,
) -> dict[str, Any]:
    """Split Sanskrit text at sandhi boundaries.

    Lighter weight than full analysis - focuses on identifying sandhi splits
    without complete disambiguation.

    Args:
        text: Sanskrit text to split (Devanagari, IAST, or SLP1).
        verbosity: Response detail level - 'minimal', 'standard', or 'detailed'.
                   Defaults to 'standard'.

    Returns:
        Dictionary with sandhi splits including:
        - original_text: The input text
        - scripts: Text in multiple scripts
        - sandhi_groups: List of sandhi-joined units with split words
        - total_words: Total number of base words found
    """
    verbosity = (verbosity or "standard").lower()

    result = await _run_analysis(text, AnalysisMode.PRODUCTION)
    if isinstance(result, dict):
        return result

    return _format_sandhi_response(result, verbosity)


def _format_sandhi_response(tree: Any, verbosity: str) -> dict[str, Any]:
    """Format AnalysisTree as sandhi-focused response."""
    response: dict[str, Any] = {
        "success": True,
        "original_text": tree.original_text,
        "scripts": _scripts_dict(tree.scripts),
    }

    best_parse = tree.best_parse
    if not best_parse:
        response["sandhi_groups"] = []
        response["total_words"] = 0
        return response

    sandhi_groups = []
    total_words = 0

    for sg in best_parse.sandhi_groups:
        sg_data: dict[str, Any] = {
            "surface_form": sg.surface_form,
            "words": [bw.lemma for bw in sg.base_words],
        }
        total_words += len(sg.base_words)

        if verbosity != "minimal":
            # Include sandhi rule if available
            if sg.sandhi_type:
                sg_data["sandhi_type"] = sg.sandhi_type.value
            if sg.sandhi_rule:
                sg_data["sandhi_rule"] = sg.sandhi_rule

        if verbosity == "detailed":
            # Include word scripts in detailed mode
            sg_data["word_details"] = [
                {
                    "lemma": bw.lemma,
                    "surface_form": bw.surface_form,
                    "scripts": {
                        "devanagari": bw.scripts.devanagari if bw.scripts else None,
                        "iast": bw.scripts.iast if bw.scripts else None,
                    },
                }
                for bw in sg.base_words
            ]

        sandhi_groups.append(sg_data)

    response["sandhi_groups"] = sandhi_groups
    response["total_words"] = total_words

    return response
