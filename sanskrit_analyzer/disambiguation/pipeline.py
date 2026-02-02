"""Disambiguation pipeline combining rules, LLM, and human review."""

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

from sanskrit_analyzer.disambiguation.llm import LLMConfig, LLMDisambiguator
from sanskrit_analyzer.disambiguation.rules import (
    ParseCandidate,
    RuleBasedDisambiguator,
    RuleBasedDisambiguatorConfig,
)

logger = logging.getLogger(__name__)


class DisambiguationStage(Enum):
    """Stage at which disambiguation was resolved."""

    NONE = "none"
    RULES = "rules"
    LLM = "llm"
    HUMAN = "human"


@dataclass
class HumanReviewConfig:
    """Configuration for human review stage."""

    enabled: bool = False
    queue_name: str = "disambiguation_queue"
    auto_flag_threshold: float = 0.5


@dataclass
class PipelineConfig:
    """Configuration for the disambiguation pipeline."""

    # Rule-based stage
    rules_enabled: bool = True
    rules_config: RuleBasedDisambiguatorConfig = field(
        default_factory=RuleBasedDisambiguatorConfig
    )

    # LLM stage
    llm_enabled: bool = True
    llm_config: LLMConfig = field(default_factory=LLMConfig)
    llm_skip_threshold: float = 0.95  # Skip LLM if confidence > this

    # Human review stage
    human_review: HumanReviewConfig = field(default_factory=HumanReviewConfig)

    # General settings
    min_candidates_for_disambiguation: int = 2
    max_disambiguation_attempts: int = 3


@dataclass
class PipelineResult:
    """Result from the disambiguation pipeline."""

    candidates: list[ParseCandidate]
    resolved_at: DisambiguationStage
    confidence: float
    needs_human_review: bool = False
    human_review_reason: Optional[str] = None
    rule_results: list[Any] = field(default_factory=list)
    llm_result: Optional[Any] = None
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def is_ambiguous(self) -> bool:
        """Check if result is still ambiguous."""
        return len(self.candidates) > 1 and self.confidence < 0.9

    @property
    def best_candidate(self) -> Optional[ParseCandidate]:
        """Get the best candidate (highest confidence)."""
        if not self.candidates:
            return None
        return max(self.candidates, key=lambda c: c.confidence)


class DisambiguationPipeline:
    """Pipeline for multi-stage disambiguation.

    The pipeline runs disambiguation in stages:
    1. Rule-based: Fast, deterministic filtering
    2. LLM: Semantic understanding (if still ambiguous)
    3. Human review: Flag for manual review (if enabled)

    Each stage can be skipped based on configuration and confidence.

    Example:
        config = PipelineConfig()
        pipeline = DisambiguationPipeline(config)
        result = await pipeline.disambiguate(candidates)
    """

    def __init__(self, config: Optional[PipelineConfig] = None) -> None:
        """Initialize the disambiguation pipeline.

        Args:
            config: Pipeline configuration.
        """
        self._config = config or PipelineConfig()

        # Initialize rule-based disambiguator
        self._rules: Optional[RuleBasedDisambiguator] = None
        if self._config.rules_enabled:
            self._rules = RuleBasedDisambiguator(self._config.rules_config)

        # Initialize LLM disambiguator
        self._llm: Optional[LLMDisambiguator] = None
        if self._config.llm_enabled:
            self._llm = LLMDisambiguator(self._config.llm_config)

    @property
    def config(self) -> PipelineConfig:
        """Get pipeline configuration."""
        return self._config

    def _get_top_confidence(self, candidates: list[ParseCandidate]) -> float:
        """Get confidence of top candidate."""
        if not candidates:
            return 0.0
        return max(c.confidence for c in candidates)

    def _should_skip_llm(self, candidates: list[ParseCandidate]) -> bool:
        """Check if LLM stage should be skipped."""
        if not self._config.llm_enabled:
            return True
        if len(candidates) <= 1:
            return True

        top_confidence = self._get_top_confidence(candidates)
        return top_confidence >= self._config.llm_skip_threshold

    def _should_flag_human(
        self, candidates: list[ParseCandidate], resolved_at: DisambiguationStage
    ) -> tuple[bool, Optional[str]]:
        """Check if result should be flagged for human review."""
        if not self._config.human_review.enabled:
            return False, None

        # Flag if still ambiguous after all stages
        if len(candidates) > 1:
            top_confidence = self._get_top_confidence(candidates)
            if top_confidence < self._config.human_review.auto_flag_threshold:
                return True, "Low confidence after all disambiguation stages"

        # Flag if resolved only by LLM with moderate confidence
        if resolved_at == DisambiguationStage.LLM:
            if candidates and candidates[0].confidence < 0.8:
                return True, "LLM disambiguation with moderate confidence"

        return False, None

    async def disambiguate(
        self,
        candidates: list[ParseCandidate],
        context: Optional[dict[str, Any]] = None,
    ) -> PipelineResult:
        """Run the full disambiguation pipeline.

        Args:
            candidates: Parse candidates to disambiguate.
            context: Optional context for disambiguation.

        Returns:
            PipelineResult with disambiguated candidates.
        """
        if not candidates:
            return PipelineResult(
                candidates=[],
                resolved_at=DisambiguationStage.NONE,
                confidence=0.0,
            )

        # If only one candidate, no disambiguation needed
        if len(candidates) < self._config.min_candidates_for_disambiguation:
            return PipelineResult(
                candidates=candidates,
                resolved_at=DisambiguationStage.NONE,
                confidence=candidates[0].confidence if candidates else 0.0,
            )

        current = candidates.copy()
        resolved_at = DisambiguationStage.NONE
        rule_results: list[Any] = []
        llm_result = None

        # Stage 1: Rule-based disambiguation
        if self._rules is not None:
            logger.debug("Running rule-based disambiguation on %d candidates", len(current))
            current = self._rules.disambiguate(current, context)
            rule_results = self._rules.last_results

            if len(current) == 1 or self._get_top_confidence(current) >= 0.95:
                resolved_at = DisambiguationStage.RULES
                logger.debug("Resolved by rules with confidence %.2f",
                           self._get_top_confidence(current))

        # Stage 2: LLM disambiguation
        if resolved_at == DisambiguationStage.NONE and not self._should_skip_llm(current):
            if self._llm is not None:
                logger.debug("Running LLM disambiguation on %d candidates", len(current))
                current, llm_result = await self._llm.disambiguate(current, context)

                if llm_result.success and len(current) >= 1:
                    resolved_at = DisambiguationStage.LLM
                    logger.debug("Resolved by LLM with ranking: %s",
                               llm_result.ranked_indices)

        # Check for human review
        needs_review, review_reason = self._should_flag_human(current, resolved_at)

        # Build result
        return PipelineResult(
            candidates=current,
            resolved_at=resolved_at,
            confidence=self._get_top_confidence(current),
            needs_human_review=needs_review,
            human_review_reason=review_reason,
            rule_results=rule_results,
            llm_result=llm_result,
        )

    async def disambiguate_single(
        self,
        candidates: list[ParseCandidate],
        context: Optional[dict[str, Any]] = None,
    ) -> Optional[ParseCandidate]:
        """Disambiguate and return the single best candidate.

        Args:
            candidates: Parse candidates to disambiguate.
            context: Optional context for disambiguation.

        Returns:
            Best candidate or None if no candidates.
        """
        result = await self.disambiguate(candidates, context)
        return result.best_candidate

    def get_stage_status(self) -> dict[str, bool]:
        """Get enabled status of each stage.

        Returns:
            Dictionary with stage enabled status.
        """
        return {
            "rules": self._rules is not None,
            "llm": self._llm is not None,
            "human_review": self._config.human_review.enabled,
        }

    async def health_check(self) -> dict[str, bool]:
        """Check health of all stages.

        Returns:
            Dictionary with stage health status.
        """
        health: dict[str, bool] = {}

        health["rules"] = self._rules is not None

        if self._llm is not None:
            health["llm"] = await self._llm.health_check()
        else:
            health["llm"] = False

        health["human_review"] = self._config.human_review.enabled

        return health
