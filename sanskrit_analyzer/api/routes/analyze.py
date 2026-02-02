"""Analyze API endpoints for Sanskrit text analysis."""

from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from sanskrit_analyzer.config import AnalysisMode

router = APIRouter(prefix="/api/v1", tags=["Analysis"])


class AnalyzeRequest(BaseModel):
    """Request model for text analysis."""

    text: str = Field(..., description="Sanskrit text to analyze", min_length=1, max_length=10000)
    mode: str = Field(
        default="production",
        description="Analysis mode: production, educational, or academic",
    )
    return_all_parses: bool = Field(
        default=False,
        description="Whether to return all possible parse trees",
    )
    context: str | None = Field(
        default=None,
        description="Optional context for disambiguation",
    )
    engines: list[str] | None = Field(
        default=None,
        description="Optional list of engines to use (vidyut, dharmamitra, heritage)",
    )
    bypass_cache: bool = Field(
        default=False,
        description="Whether to bypass cache and force re-analysis",
    )

    model_config = {"json_schema_extra": {"example": {"text": "रामः गच्छति", "mode": "production"}}}


class ScriptVariantsResponse(BaseModel):
    """Script variants for a text."""

    devanagari: str
    iast: str
    slp1: str
    itrans: str | None = None


class MorphologicalTagResponse(BaseModel):
    """Morphological analysis of a word."""

    pos: str | None = None
    gender: str | None = None
    number: str | None = None
    case: str | None = None
    person: str | None = None
    tense: str | None = None
    mood: str | None = None
    voice: str | None = None


class DhatuInfoResponse(BaseModel):
    """Dhatu (verbal root) information."""

    dhatu: str
    meaning: str | None = None
    gana: int | None = None
    pada: str | None = None


class BaseWordResponse(BaseModel):
    """A base word in the analysis."""

    word_id: str
    lemma: str
    surface_form: str
    scripts: ScriptVariantsResponse | None = None
    morphology: MorphologicalTagResponse | None = None
    meanings: list[str] = []
    dhatu: DhatuInfoResponse | None = None
    confidence: float


class SandhiGroupResponse(BaseModel):
    """A group of words joined by sandhi."""

    group_id: str
    surface_form: str
    base_words: list[BaseWordResponse]


class ParseTreeResponse(BaseModel):
    """A single parse tree (interpretation)."""

    parse_id: str
    confidence: float
    sandhi_groups: list[SandhiGroupResponse] = []
    is_selected: bool = False


class ConfidenceMetricsResponse(BaseModel):
    """Confidence metrics for the analysis."""

    overall: float
    engine_agreement: float
    disambiguation_score: float | None = None


class AnalysisTreeResponse(BaseModel):
    """Complete analysis response."""

    sentence_id: str
    original_text: str
    normalized_slp1: str
    scripts: ScriptVariantsResponse
    parse_forest: list[ParseTreeResponse]
    confidence: ConfidenceMetricsResponse
    mode: str
    cached_at: str | None = None
    needs_human_review: bool = False
    engine_details: dict[str, Any] | None = None


class DisambiguateRequest(BaseModel):
    """Request to save disambiguation choice."""

    sentence_id: str = Field(..., description="The sentence ID from analysis")
    selected_parse: str = Field(..., description="The parse_id of the selected interpretation")


def _tree_to_response(tree: Any) -> AnalysisTreeResponse:
    """Convert AnalysisTree to response model."""
    # Convert scripts
    scripts = ScriptVariantsResponse(
        devanagari=tree.scripts.devanagari,
        iast=tree.scripts.iast,
        slp1=tree.scripts.slp1,
        itrans=getattr(tree.scripts, "itrans", None),
    )

    # Convert parse forest
    parse_forest = []
    for pt_idx, pt in enumerate(tree.parse_forest):
        sandhi_groups = []
        for sg_idx, sg in enumerate(pt.sandhi_groups):
            base_words = []
            for bw_idx, bw in enumerate(sg.base_words):
                # Convert morphology
                morph_resp = None
                if bw.morphology:
                    morph_resp = MorphologicalTagResponse(
                        pos=getattr(bw.morphology, "pos", None),
                        gender=getattr(bw.morphology, "gender", None),
                        number=getattr(bw.morphology, "number", None),
                        case=getattr(bw.morphology, "case", None),
                        person=getattr(bw.morphology, "person", None),
                        tense=getattr(bw.morphology, "tense", None),
                        mood=getattr(bw.morphology, "mood", None),
                        voice=getattr(bw.morphology, "voice", None),
                    )

                # Convert dhatu
                dhatu_resp = None
                if bw.dhatu:
                    dhatu_resp = DhatuInfoResponse(
                        dhatu=bw.dhatu.dhatu,
                        meaning=bw.dhatu.meaning,
                        gana=bw.dhatu.gana,
                        pada=bw.dhatu.pada,
                    )

                # Convert scripts
                bw_scripts = None
                if bw.scripts:
                    bw_scripts = ScriptVariantsResponse(
                        devanagari=bw.scripts.devanagari,
                        iast=bw.scripts.iast,
                        slp1=bw.scripts.slp1,
                    )

                # Generate word_id if not present
                word_id = getattr(bw, "word_id", None) or f"w{pt_idx}_{sg_idx}_{bw_idx}"

                # Handle meanings - may be list of Meaning objects or strings
                meanings = []
                if bw.meanings:
                    for m in bw.meanings:
                        meanings.append(str(m) if not isinstance(m, str) else m)

                base_words.append(
                    BaseWordResponse(
                        word_id=word_id,
                        lemma=bw.lemma,
                        surface_form=bw.surface_form,
                        scripts=bw_scripts,
                        morphology=morph_resp,
                        meanings=meanings,
                        dhatu=dhatu_resp,
                        confidence=bw.confidence,
                    )
                )

            # Generate group_id if not present
            group_id = getattr(sg, "group_id", None) or f"g{pt_idx}_{sg_idx}"

            sandhi_groups.append(
                SandhiGroupResponse(
                    group_id=group_id,
                    surface_form=sg.surface_form,
                    base_words=base_words,
                )
            )

        parse_forest.append(
            ParseTreeResponse(
                parse_id=pt.parse_id,
                confidence=pt.confidence,
                sandhi_groups=sandhi_groups,
                is_selected=getattr(pt, "is_selected", False),
            )
        )

    # Convert confidence
    confidence = ConfidenceMetricsResponse(
        overall=tree.confidence.overall,
        engine_agreement=tree.confidence.engine_agreement,
        disambiguation_score=getattr(tree.confidence, "disambiguation_score", None),
    )

    return AnalysisTreeResponse(
        sentence_id=tree.sentence_id,
        original_text=tree.original_text,
        normalized_slp1=tree.normalized_slp1,
        scripts=scripts,
        parse_forest=parse_forest,
        confidence=confidence,
        mode=getattr(tree, "mode", "production"),
        cached_at=tree.cached_at.value if tree.cached_at else None,
        needs_human_review=getattr(tree, "needs_human_review", False),
        engine_details=getattr(tree, "engine_details", None),
    )


@router.post("/analyze", response_model=AnalysisTreeResponse)
async def analyze_text(request: Request, body: AnalyzeRequest) -> AnalysisTreeResponse:
    """Analyze Sanskrit text and return parse tree.

    Returns a hierarchical analysis with:
    - Sandhi groups (compounds)
    - Base words with morphological analysis
    - Dhatu information for verbs
    - Confidence scores from ensemble voting
    """
    analyzer = request.app.state.analyzer

    # Validate mode
    try:
        mode = AnalysisMode(body.mode.lower())
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid mode: {body.mode}. Must be one of: production, educational, academic",
        )

    # Perform analysis
    tree = await analyzer.analyze(
        text=body.text,
        mode=mode,
        return_all_parses=body.return_all_parses,
        context=body.context,
        engines=body.engines,
        bypass_cache=body.bypass_cache,
    )

    return _tree_to_response(tree)


@router.get("/analyze/{sentence_id}", response_model=AnalysisTreeResponse)
async def get_analysis(request: Request, sentence_id: str) -> AnalysisTreeResponse:
    """Retrieve a cached analysis by sentence ID.

    Returns the previously computed analysis if it exists in cache.
    """
    analyzer = request.app.state.analyzer

    # Try to get from cache
    if analyzer._cache is None:
        raise HTTPException(status_code=404, detail="Caching not enabled")

    # Look up in SQLite corpus by sentence_id
    if analyzer._cache._sqlite is None:
        raise HTTPException(status_code=404, detail="Corpus storage not enabled")

    result = analyzer._cache._sqlite.get_by_id(sentence_id)
    if result is None:
        raise HTTPException(status_code=404, detail=f"Analysis not found: {sentence_id}")

    # Reconstruct tree from cached data
    tree = analyzer._result_to_tree(result, None)
    return _tree_to_response(tree)


@router.post("/disambiguate", response_model=AnalysisTreeResponse)
async def save_disambiguation(
    request: Request,
    body: DisambiguateRequest,
) -> AnalysisTreeResponse:
    """Save a human disambiguation choice.

    Updates the corpus with the selected parse interpretation.
    """
    analyzer = request.app.state.analyzer

    if analyzer._cache is None or analyzer._cache._sqlite is None:
        raise HTTPException(status_code=400, detail="Corpus storage not enabled")

    # Get the existing analysis
    result = analyzer._cache._sqlite.get_by_id(body.sentence_id)
    if result is None:
        raise HTTPException(status_code=404, detail=f"Analysis not found: {body.sentence_id}")

    # Update with selected parse
    analyzer._cache._sqlite.set_disambiguation(
        body.sentence_id,
        body.selected_parse,
        "human",
    )

    # Return updated tree
    updated = analyzer._cache._sqlite.get_by_id(body.sentence_id)
    tree = analyzer._result_to_tree(updated, None)
    return _tree_to_response(tree)
