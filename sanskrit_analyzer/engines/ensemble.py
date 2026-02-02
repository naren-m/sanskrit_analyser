"""Ensemble analyzer combining multiple analysis engines."""

import asyncio
from dataclasses import dataclass, field
from typing import Optional

from sanskrit_analyzer.engines.base import EngineBase, EngineResult, Segment


@dataclass
class EnsembleConfig:
    """Configuration for the ensemble analyzer."""

    vidyut_weight: float = 0.35
    dharmamitra_weight: float = 0.40
    heritage_weight: float = 0.25
    min_agreement_for_high_confidence: float = 0.95
    min_agreement_for_medium_confidence: float = 0.70


@dataclass
class MergedSegment:
    """A segment merged from multiple engine results."""

    surface: str
    lemma: str
    morphology: Optional[str] = None
    confidence: float = 0.0
    pos: Optional[str] = None
    meanings: list[str] = field(default_factory=list)
    engine_votes: dict[str, float] = field(default_factory=dict)
    agreement_score: float = 0.0

    def to_segment(self) -> Segment:
        """Convert to base Segment."""
        return Segment(
            surface=self.surface,
            lemma=self.lemma,
            morphology=self.morphology,
            confidence=self.confidence,
            pos=self.pos,
            meanings=self.meanings,
        )


@dataclass
class EnsembleResult:
    """Result from ensemble analysis."""

    segments: list[MergedSegment] = field(default_factory=list)
    engine_results: dict[str, EngineResult] = field(default_factory=dict)
    overall_confidence: float = 0.0
    agreement_level: str = "low"  # "high", "medium", "low"
    errors: list[str] = field(default_factory=list)

    @property
    def success(self) -> bool:
        """Check if analysis succeeded."""
        return len(self.segments) > 0

    @property
    def available_engines(self) -> list[str]:
        """Get list of engines that produced results."""
        return [name for name, result in self.engine_results.items() if result.success]


class EnsembleAnalyzer:
    """Combines multiple analysis engines with weighted voting.

    The ensemble analyzer runs multiple engines in parallel and combines
    their results using configurable weights:
    - Vidyut (Paninian rules): 0.35
    - Dharmamitra (Neural): 0.40
    - Heritage (Lexicon): 0.25

    Agreement scoring:
    - All 3 agree: High confidence (0.95+)
    - 2 of 3 agree: Medium confidence (0.70-0.95)
    - All differ: Low confidence (<0.70)
    """

    def __init__(
        self,
        engines: Optional[list[EngineBase]] = None,
        config: Optional[EnsembleConfig] = None,
    ) -> None:
        """Initialize the ensemble analyzer.

        Args:
            engines: List of analysis engines to use.
            config: Ensemble configuration.
        """
        self._engines: list[EngineBase] = engines or []
        self._config = config or EnsembleConfig()
        self._weights: dict[str, float] = {}

        # Set up weights
        self._weights = {
            "vidyut": self._config.vidyut_weight,
            "dharmamitra": self._config.dharmamitra_weight,
            "heritage": self._config.heritage_weight,
        }

    def add_engine(self, engine: EngineBase) -> None:
        """Add an engine to the ensemble.

        Args:
            engine: Engine to add.
        """
        self._engines.append(engine)
        if engine.name not in self._weights:
            self._weights[engine.name] = engine.weight

    def remove_engine(self, name: str) -> None:
        """Remove an engine from the ensemble.

        Args:
            name: Name of engine to remove.
        """
        self._engines = [e for e in self._engines if e.name != name]

    @property
    def engine_names(self) -> list[str]:
        """Get names of all engines in the ensemble."""
        return [e.name for e in self._engines]

    @property
    def available_engines(self) -> list[str]:
        """Get names of available engines."""
        return [e.name for e in self._engines if e.is_available]

    async def analyze(self, text: str) -> EnsembleResult:
        """Analyze text using all engines and combine results.

        Args:
            text: Sanskrit text to analyze.

        Returns:
            EnsembleResult with merged segments and agreement info.
        """
        if not self._engines:
            return EnsembleResult(
                errors=["No engines configured"],
            )

        # Run all engines in parallel
        tasks = []
        for engine in self._engines:
            if engine.is_available:
                tasks.append(self._run_engine(engine, text))

        if not tasks:
            return EnsembleResult(
                errors=["No available engines"],
            )

        # Gather results, handling exceptions
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Collect successful results
        engine_results: dict[str, EngineResult] = {}
        errors: list[str] = []

        for result in results:
            if isinstance(result, Exception):
                errors.append(str(result))
            elif isinstance(result, EngineResult):
                engine_results[result.engine] = result
                if result.error:
                    errors.append(f"{result.engine}: {result.error}")

        if not engine_results:
            return EnsembleResult(
                errors=errors or ["All engines failed"],
            )

        # Merge results
        merged_segments = self._merge_results(engine_results)

        # Calculate overall confidence and agreement
        agreement_level, overall_confidence = self._calculate_agreement(
            engine_results, merged_segments
        )

        return EnsembleResult(
            segments=merged_segments,
            engine_results=engine_results,
            overall_confidence=overall_confidence,
            agreement_level=agreement_level,
            errors=errors,
        )

    async def _run_engine(self, engine: EngineBase, text: str) -> EngineResult:
        """Run a single engine with error handling.

        Args:
            engine: Engine to run.
            text: Text to analyze.

        Returns:
            EngineResult from the engine.
        """
        try:
            return await engine.analyze(text)
        except Exception as e:
            return EngineResult(
                engine=engine.name,
                segments=[],
                confidence=0.0,
                error=f"Engine error: {e}",
            )

    def _merge_results(
        self, engine_results: dict[str, EngineResult]
    ) -> list[MergedSegment]:
        """Merge results from multiple engines.

        Uses the engine with the most segments as the base, then
        enriches with information from other engines.

        Args:
            engine_results: Results from each engine.

        Returns:
            List of merged segments.
        """
        if not engine_results:
            return []

        # Find the result with the most segments (primary)
        primary_engine = max(
            engine_results.keys(),
            key=lambda name: len(engine_results[name].segments),
        )
        primary_result = engine_results[primary_engine]

        if not primary_result.segments:
            return []

        # Build merged segments
        merged: list[MergedSegment] = []

        for i, seg in enumerate(primary_result.segments):
            # Collect votes from all engines for this segment
            votes: dict[str, float] = {}
            all_lemmas: list[str] = []
            all_meanings: list[str] = []
            all_morphologies: list[str] = []
            all_pos: list[str] = []

            for engine_name, result in engine_results.items():
                if i < len(result.segments):
                    other_seg = result.segments[i]
                    weight = self._weights.get(engine_name, 0.33)
                    votes[engine_name] = other_seg.confidence * weight

                    if other_seg.lemma:
                        all_lemmas.append(other_seg.lemma)
                    if other_seg.meanings:
                        all_meanings.extend(other_seg.meanings)
                    if other_seg.morphology:
                        all_morphologies.append(other_seg.morphology)
                    if other_seg.pos:
                        all_pos.append(other_seg.pos)

            # Calculate weighted confidence
            total_weight = sum(self._weights.get(name, 0.33) for name in votes.keys())
            weighted_confidence = (
                sum(votes.values()) / total_weight if total_weight > 0 else 0.0
            )

            # Choose most common lemma (or primary)
            best_lemma = seg.lemma
            if all_lemmas:
                lemma_counts: dict[str, int] = {}
                for lemma in all_lemmas:
                    lemma_counts[lemma] = lemma_counts.get(lemma, 0) + 1
                best_lemma = max(lemma_counts.keys(), key=lambda x: lemma_counts[x])

            # Calculate agreement score
            agreement = self._calculate_lemma_agreement(all_lemmas)

            merged_segment = MergedSegment(
                surface=seg.surface,
                lemma=best_lemma,
                morphology=all_morphologies[0] if all_morphologies else seg.morphology,
                confidence=weighted_confidence,
                pos=all_pos[0] if all_pos else seg.pos,
                meanings=list(set(all_meanings)),  # Deduplicate
                engine_votes=votes,
                agreement_score=agreement,
            )

            merged.append(merged_segment)

        return merged

    def _calculate_lemma_agreement(self, lemmas: list[str]) -> float:
        """Calculate agreement score for a list of lemmas.

        Args:
            lemmas: List of lemmas from different engines.

        Returns:
            Agreement score (0.0 to 1.0).
        """
        if not lemmas:
            return 0.0
        if len(lemmas) == 1:
            return 1.0

        # Count unique lemmas
        unique = set(lemmas)

        # Perfect agreement if all the same
        if len(unique) == 1:
            return 1.0

        # Partial agreement based on most common
        counts: dict[str, int] = {}
        for lemma in lemmas:
            counts[lemma] = counts.get(lemma, 0) + 1

        max_count = max(counts.values())
        return float(max_count) / len(lemmas)

    def _calculate_agreement(
        self,
        engine_results: dict[str, EngineResult],
        merged_segments: list[MergedSegment],
    ) -> tuple[str, float]:
        """Calculate overall agreement level and confidence.

        Args:
            engine_results: Results from each engine.
            merged_segments: Merged segment list.

        Returns:
            Tuple of (agreement_level, overall_confidence).
        """
        if not merged_segments:
            return "low", 0.0

        # Average agreement across segments
        avg_agreement = sum(s.agreement_score for s in merged_segments) / len(
            merged_segments
        )

        # Average confidence
        avg_confidence = sum(s.confidence for s in merged_segments) / len(
            merged_segments
        )

        # Determine agreement level
        if avg_agreement >= self._config.min_agreement_for_high_confidence:
            return "high", min(0.95, avg_confidence)
        elif avg_agreement >= self._config.min_agreement_for_medium_confidence:
            return "medium", min(0.85, avg_confidence)
        else:
            return "low", avg_confidence

    @classmethod
    def create_default(cls) -> "EnsembleAnalyzer":
        """Create an ensemble with all default engines.

        Returns:
            EnsembleAnalyzer with Vidyut, Dharmamitra, and Heritage engines.
        """
        from sanskrit_analyzer.engines.dharmamitra_engine import DharmamitraEngine
        from sanskrit_analyzer.engines.heritage_engine import HeritageEngine
        from sanskrit_analyzer.engines.vidyut_engine import VidyutEngine

        return cls(
            engines=[
                VidyutEngine(),
                DharmamitraEngine(),
                HeritageEngine(),
            ]
        )
