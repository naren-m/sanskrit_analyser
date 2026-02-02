"""Tests for disambiguation pipeline."""

import pytest

from sanskrit_analyzer.disambiguation.llm import LLMConfig, LLMDisambiguationResult
from sanskrit_analyzer.disambiguation.pipeline import (
    DisambiguationPipeline,
    DisambiguationStage,
    HumanReviewConfig,
    PipelineConfig,
    PipelineResult,
)
from sanskrit_analyzer.disambiguation.rules import ParseCandidate


class TestPipelineConfig:
    """Tests for PipelineConfig dataclass."""

    def test_defaults(self) -> None:
        """Test default configuration."""
        config = PipelineConfig()
        assert config.rules_enabled is True
        assert config.llm_enabled is True
        assert config.llm_skip_threshold == 0.95
        assert config.human_review.enabled is False

    def test_custom_config(self) -> None:
        """Test custom configuration."""
        config = PipelineConfig(
            rules_enabled=False,
            llm_skip_threshold=0.8,
            human_review=HumanReviewConfig(enabled=True),
        )
        assert config.rules_enabled is False
        assert config.llm_skip_threshold == 0.8
        assert config.human_review.enabled is True


class TestHumanReviewConfig:
    """Tests for HumanReviewConfig dataclass."""

    def test_defaults(self) -> None:
        """Test default configuration."""
        config = HumanReviewConfig()
        assert config.enabled is False
        assert config.queue_name == "disambiguation_queue"
        assert config.auto_flag_threshold == 0.5


class TestPipelineResult:
    """Tests for PipelineResult dataclass."""

    def test_is_ambiguous(self) -> None:
        """Test ambiguity check."""
        # Not ambiguous - single candidate
        result1 = PipelineResult(
            candidates=[ParseCandidate(index=0, segments=[], confidence=0.9)],
            resolved_at=DisambiguationStage.RULES,
            confidence=0.9,
        )
        assert result1.is_ambiguous is False

        # Ambiguous - multiple candidates with low confidence
        result2 = PipelineResult(
            candidates=[
                ParseCandidate(index=0, segments=[], confidence=0.6),
                ParseCandidate(index=1, segments=[], confidence=0.5),
            ],
            resolved_at=DisambiguationStage.RULES,
            confidence=0.6,
        )
        assert result2.is_ambiguous is True

        # Not ambiguous - high confidence
        result3 = PipelineResult(
            candidates=[
                ParseCandidate(index=0, segments=[], confidence=0.95),
                ParseCandidate(index=1, segments=[], confidence=0.5),
            ],
            resolved_at=DisambiguationStage.RULES,
            confidence=0.95,
        )
        assert result3.is_ambiguous is False

    def test_best_candidate(self) -> None:
        """Test getting best candidate."""
        candidates = [
            ParseCandidate(index=0, segments=[], confidence=0.7),
            ParseCandidate(index=1, segments=[], confidence=0.9),
            ParseCandidate(index=2, segments=[], confidence=0.8),
        ]
        result = PipelineResult(
            candidates=candidates,
            resolved_at=DisambiguationStage.RULES,
            confidence=0.9,
        )
        best = result.best_candidate
        assert best is not None
        assert best.index == 1

    def test_best_candidate_empty(self) -> None:
        """Test best candidate with no candidates."""
        result = PipelineResult(
            candidates=[],
            resolved_at=DisambiguationStage.NONE,
            confidence=0.0,
        )
        assert result.best_candidate is None


class TestDisambiguationPipeline:
    """Tests for DisambiguationPipeline class."""

    @pytest.fixture
    def pipeline(self) -> DisambiguationPipeline:
        """Create a pipeline instance with LLM disabled."""
        config = PipelineConfig(llm_enabled=False)
        return DisambiguationPipeline(config)

    @pytest.fixture
    def candidates(self) -> list[ParseCandidate]:
        """Create test candidates."""
        return [
            ParseCandidate(
                index=0,
                segments=[{"lemma": "gam", "pos": "verb"}],
                confidence=0.8,
            ),
            ParseCandidate(
                index=1,
                segments=[{"lemma": "rare_word", "pos": "noun"}],
                confidence=0.7,
            ),
        ]

    def test_init(self, pipeline: DisambiguationPipeline) -> None:
        """Test initialization."""
        status = pipeline.get_stage_status()
        assert status["rules"] is True
        assert status["llm"] is False

    @pytest.mark.asyncio
    async def test_empty_candidates(
        self, pipeline: DisambiguationPipeline
    ) -> None:
        """Test with no candidates."""
        result = await pipeline.disambiguate([])
        assert result.candidates == []
        assert result.resolved_at == DisambiguationStage.NONE
        assert result.confidence == 0.0

    @pytest.mark.asyncio
    async def test_single_candidate(
        self, pipeline: DisambiguationPipeline
    ) -> None:
        """Test with single candidate."""
        candidates = [
            ParseCandidate(index=0, segments=[], confidence=0.9)
        ]
        result = await pipeline.disambiguate(candidates)
        assert len(result.candidates) == 1
        assert result.resolved_at == DisambiguationStage.NONE

    @pytest.mark.asyncio
    async def test_rules_stage(
        self, pipeline: DisambiguationPipeline, candidates: list[ParseCandidate]
    ) -> None:
        """Test rule-based disambiguation."""
        result = await pipeline.disambiguate(candidates)

        # Rules should have run
        assert len(result.rule_results) > 0
        # Common lemma should be ranked higher
        assert result.candidates[0].segments[0]["lemma"] == "gam"

    @pytest.mark.asyncio
    async def test_high_confidence_skips_llm(
        self, candidates: list[ParseCandidate]
    ) -> None:
        """Test that high confidence skips LLM."""
        # Set first candidate to very high confidence
        candidates[0].confidence = 0.98

        config = PipelineConfig(llm_enabled=True)
        pipeline = DisambiguationPipeline(config)

        # Mock LLM to track if called
        llm_called = False

        async def mock_disambiguate(cands, ctx):
            nonlocal llm_called
            llm_called = True
            return cands, LLMDisambiguationResult(success=True)

        if pipeline._llm:
            pipeline._llm.disambiguate = mock_disambiguate  # type: ignore

        result = await pipeline.disambiguate(candidates)

        # LLM should have been skipped
        assert llm_called is False

    @pytest.mark.asyncio
    async def test_llm_stage(self, candidates: list[ParseCandidate]) -> None:
        """Test LLM disambiguation stage."""
        config = PipelineConfig(
            rules_enabled=False,  # Skip rules
            llm_enabled=True,
            llm_skip_threshold=1.0,  # Never skip LLM
        )
        pipeline = DisambiguationPipeline(config)

        # Mock LLM response
        async def mock_disambiguate(cands, ctx):
            # Reorder candidates
            reordered = [cands[1], cands[0]]
            return reordered, LLMDisambiguationResult(
                success=True,
                ranked_indices=[1, 0],
            )

        if pipeline._llm:
            pipeline._llm.disambiguate = mock_disambiguate  # type: ignore

        result = await pipeline.disambiguate(candidates)

        assert result.resolved_at == DisambiguationStage.LLM
        assert result.llm_result is not None
        # Order should be reversed
        assert result.candidates[0].index == 1

    @pytest.mark.asyncio
    async def test_human_review_flag(
        self, candidates: list[ParseCandidate]
    ) -> None:
        """Test human review flagging."""
        config = PipelineConfig(
            llm_enabled=False,
            human_review=HumanReviewConfig(
                enabled=True,
                auto_flag_threshold=0.9,  # High threshold
            ),
        )
        pipeline = DisambiguationPipeline(config)

        # Set low confidence
        for c in candidates:
            c.confidence = 0.4

        result = await pipeline.disambiguate(candidates)

        assert result.needs_human_review is True
        assert result.human_review_reason is not None

    @pytest.mark.asyncio
    async def test_human_review_disabled(
        self, pipeline: DisambiguationPipeline, candidates: list[ParseCandidate]
    ) -> None:
        """Test that human review is disabled by default."""
        for c in candidates:
            c.confidence = 0.3  # Low confidence

        result = await pipeline.disambiguate(candidates)

        assert result.needs_human_review is False

    @pytest.mark.asyncio
    async def test_disambiguate_single(
        self, pipeline: DisambiguationPipeline, candidates: list[ParseCandidate]
    ) -> None:
        """Test single candidate disambiguation."""
        best = await pipeline.disambiguate_single(candidates)

        assert best is not None
        assert isinstance(best, ParseCandidate)

    @pytest.mark.asyncio
    async def test_health_check(self) -> None:
        """Test health check."""
        config = PipelineConfig(llm_enabled=False)
        pipeline = DisambiguationPipeline(config)

        health = await pipeline.health_check()

        assert health["rules"] is True
        assert health["llm"] is False
        assert health["human_review"] is False

    def test_get_stage_status(self) -> None:
        """Test getting stage status."""
        config = PipelineConfig(
            rules_enabled=True,
            llm_enabled=True,
            human_review=HumanReviewConfig(enabled=True),
        )
        pipeline = DisambiguationPipeline(config)

        status = pipeline.get_stage_status()

        assert status["rules"] is True
        assert status["llm"] is True
        assert status["human_review"] is True

    @pytest.mark.asyncio
    async def test_all_stages_disabled(self) -> None:
        """Test with all stages disabled."""
        config = PipelineConfig(
            rules_enabled=False,
            llm_enabled=False,
        )
        pipeline = DisambiguationPipeline(config)

        candidates = [
            ParseCandidate(index=0, segments=[], confidence=0.8),
            ParseCandidate(index=1, segments=[], confidence=0.7),
        ]

        result = await pipeline.disambiguate(candidates)

        # Should return original candidates
        assert len(result.candidates) == 2
        assert result.resolved_at == DisambiguationStage.NONE

    @pytest.mark.asyncio
    async def test_context_passed_through(
        self, candidates: list[ParseCandidate]
    ) -> None:
        """Test that context is passed to stages."""
        config = PipelineConfig(
            rules_enabled=False,
            llm_enabled=True,
            llm_skip_threshold=1.0,
        )
        pipeline = DisambiguationPipeline(config)

        context = {"previous_sentence": "rāmo vanam agacchat"}
        received_context = None

        async def mock_disambiguate(cands, ctx):
            nonlocal received_context
            received_context = ctx
            return cands, LLMDisambiguationResult(success=True)

        if pipeline._llm:
            pipeline._llm.disambiguate = mock_disambiguate  # type: ignore

        await pipeline.disambiguate(candidates, context)

        assert received_context == context
