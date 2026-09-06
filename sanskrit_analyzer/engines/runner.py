"""Run the configured analysis engines and hand their segments to the tree builder.

This was a weighted-voting ensemble over Vidyut, Dharmamitra and Heritage.
Dharmamitra's API is gone and the Heritage HTML parser was never written, so
the vote always ran with a single engine and the weights never changed an
outcome.

What is left is a runner: engines run in parallel, the first *configured* one
that produced segments is the analysis, and every engine's raw result is kept
in :attr:`EngineRunResult.engine_results` for diagnostics and for callers that
want a specific engine's output (the split validator asks for vidyut's).
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field

from sanskrit_analyzer.engines.base import EngineBase, EngineResult, Segment


@dataclass
class AnalyzedSegment:
    """A segment from the primary engine, carrying the per-engine scores.

    ``engine_votes`` and ``agreement_score`` are part of the ``AnalysisTree``
    contract that downstream consumers read. With a single primary engine the
    vote is that engine's own confidence and the agreement is 1.0.
    """

    surface: str
    lemma: str
    morphology: str | None = None
    confidence: float = 0.0
    pos: str | None = None
    meanings: list[str] = field(default_factory=list)
    engine_votes: dict[str, float] = field(default_factory=dict)
    agreement_score: float = 1.0

    @classmethod
    def from_segment(cls, segment: Segment, engine: str) -> AnalyzedSegment:
        """Wrap a raw engine ``Segment`` as the analysis produced by ``engine``."""
        return cls(
            surface=segment.surface,
            lemma=segment.lemma,
            morphology=segment.morphology,
            confidence=segment.confidence,
            pos=segment.pos,
            meanings=list(segment.meanings),
            engine_votes={engine: segment.confidence},
        )


@dataclass
class EngineRunResult:
    """Result of one run over the configured engines."""

    segments: list[AnalyzedSegment] = field(default_factory=list)
    engine_results: dict[str, EngineResult] = field(default_factory=dict)
    overall_confidence: float = 0.0
    primary_engine: str | None = None
    errors: list[str] = field(default_factory=list)

    @property
    def success(self) -> bool:
        """Whether the run produced any segments."""
        return len(self.segments) > 0


class EngineRunner:
    """Runs the configured analysis engines and picks the primary result."""

    def __init__(self, engines: list[EngineBase] | None = None) -> None:
        """Initialize the runner.

        Args:
            engines: Analysis engines, in priority order. The first one that
                returns segments provides the analysis.
        """
        self._engines: list[EngineBase] = engines or []

    def add_engine(self, engine: EngineBase) -> None:
        """Append an engine (lowest priority)."""
        self._engines.append(engine)

    def remove_engine(self, name: str) -> None:
        """Remove an engine by name."""
        self._engines = [e for e in self._engines if e.name != name]

    @property
    def engine_names(self) -> list[str]:
        """Names of all configured engines, in priority order."""
        return [e.name for e in self._engines]

    @property
    def available_engines(self) -> list[str]:
        """Names of configured engines that report themselves available."""
        return [e.name for e in self._engines if e.is_available]

    async def analyze(self, text: str, engines: list[str] | None = None) -> EngineRunResult:
        """Run the engines over ``text``.

        Args:
            text: Sanskrit text to analyze.
            engines: Optional engine names to restrict this call to. Filtering
                here (rather than mutating ``self._engines``) keeps concurrent
                callers sharing one runner from racing on the engine list.

        Returns:
            EngineRunResult holding the primary engine's segments.
        """
        selected = [e for e in self._engines if not engines or e.name in engines]
        if not selected:
            return EngineRunResult(errors=["No engines configured"])

        runnable = [e for e in selected if e.is_available]
        if not runnable:
            return EngineRunResult(errors=["No available engines"])

        results = await asyncio.gather(
            *(self._run_engine(e, text) for e in runnable), return_exceptions=True
        )

        engine_results: dict[str, EngineResult] = {}
        errors: list[str] = []
        for result in results:
            if isinstance(result, BaseException):
                errors.append(str(result))
                continue
            engine_results[result.engine] = result
            if result.error:
                errors.append(f"{result.engine}: {result.error}")

        # Priority order, not "whoever returned the most segments": which engine
        # is authoritative is a configuration decision, not a race.
        primary = next(
            (r for e in runnable if (r := engine_results.get(e.name)) and r.segments),
            None,
        )
        if primary is None:
            return EngineRunResult(engine_results=engine_results, errors=errors)

        segments = [AnalyzedSegment.from_segment(s, primary.engine) for s in primary.segments]
        return EngineRunResult(
            segments=segments,
            engine_results=engine_results,
            overall_confidence=sum(s.confidence for s in segments) / len(segments),
            primary_engine=primary.engine,
            errors=errors,
        )

    async def _run_engine(self, engine: EngineBase, text: str) -> EngineResult:
        """Run a single engine, turning a raised exception into a failed result."""
        try:
            return await engine.analyze(text)
        except Exception as e:
            return EngineResult(
                engine=engine.name,
                segments=[],
                confidence=0.0,
                error=f"Engine error: {e}",
            )

    @classmethod
    def create_default(cls) -> EngineRunner:
        """Create a runner with the default (Vidyut) engine."""
        from sanskrit_analyzer.engines.vidyut_engine import VidyutEngine

        return cls(engines=[VidyutEngine()])
