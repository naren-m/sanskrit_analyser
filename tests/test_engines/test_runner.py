"""Tests for the engine runner."""

from unittest.mock import AsyncMock

import pytest

from sanskrit_analyzer.engines.base import EngineBase, EngineResult, Segment
from sanskrit_analyzer.engines.runner import AnalyzedSegment, EngineRunner


class MockEngine(EngineBase):
    """Mock engine for testing."""

    def __init__(
        self,
        name: str,
        segments: list[Segment] | None = None,
        available: bool = True,
    ) -> None:
        self._name = name
        self._segments = segments or []
        self._available = available

    @property
    def name(self) -> str:
        return self._name

    @property
    def is_available(self) -> bool:
        return self._available

    async def analyze(self, text: str) -> EngineResult:
        return EngineResult(
            engine=self._name,
            segments=self._segments,
            confidence=0.9 if self._segments else 0.0,
        )


@pytest.fixture
def segment() -> Segment:
    return Segment(surface="gacchati", lemma="gam", confidence=0.9)


class TestEngineRunner:
    """Tests for EngineRunner."""

    def test_add_engine(self) -> None:
        runner = EngineRunner()
        runner.add_engine(MockEngine("test"))
        assert "test" in runner.engine_names

    def test_remove_engine(self, segment: Segment) -> None:
        runner = EngineRunner(
            engines=[MockEngine("vidyut", [segment]), MockEngine("local_byt5", [segment])]
        )
        runner.remove_engine("vidyut")
        assert runner.engine_names == ["local_byt5"]

    def test_available_engines(self) -> None:
        runner = EngineRunner(
            engines=[
                MockEngine("available", available=True),
                MockEngine("unavailable", available=False),
            ]
        )
        assert runner.available_engines == ["available"]

    @pytest.mark.asyncio
    async def test_analyze_single_engine(self, segment: Segment) -> None:
        runner = EngineRunner(engines=[MockEngine("vidyut", [segment])])

        result = await runner.analyze("gacchati")

        assert result.success
        assert result.primary_engine == "vidyut"
        assert [s.lemma for s in result.segments] == ["gam"]
        assert result.overall_confidence == pytest.approx(0.9)

    @pytest.mark.asyncio
    async def test_vote_is_the_engines_own_confidence(self, segment: Segment) -> None:
        """No weighting: the vote is the engine's confidence, not a scaled score."""
        runner = EngineRunner(engines=[MockEngine("vidyut", [segment])])

        result = await runner.analyze("gacchati")

        assert result.segments[0].engine_votes == {"vidyut": 0.9}
        assert result.segments[0].agreement_score == 1.0

    @pytest.mark.asyncio
    async def test_primary_follows_configured_order_not_segment_count(self) -> None:
        """The first configured engine wins even when a later one splits more."""
        first = MockEngine("vidyut", [Segment(surface="test", lemma="first", confidence=0.6)])
        second = MockEngine(
            "local_byt5",
            [
                Segment(surface="te", lemma="second_a", confidence=0.99),
                Segment(surface="st", lemma="second_b", confidence=0.99),
            ],
        )
        runner = EngineRunner(engines=[first, second])

        result = await runner.analyze("test")

        assert result.primary_engine == "vidyut"
        assert [s.lemma for s in result.segments] == ["first"]
        # The other engine still ran and is reported for diagnostics.
        assert set(result.engine_results) == {"vidyut", "local_byt5"}

    @pytest.mark.asyncio
    async def test_primary_skips_engine_with_no_segments(self, segment: Segment) -> None:
        runner = EngineRunner(engines=[MockEngine("empty", []), MockEngine("vidyut", [segment])])

        result = await runner.analyze("gacchati")

        assert result.primary_engine == "vidyut"
        assert result.success

    @pytest.mark.asyncio
    async def test_analyze_no_engines(self) -> None:
        result = await EngineRunner(engines=[]).analyze("test")

        assert not result.success
        assert "No engines configured" in result.errors

    @pytest.mark.asyncio
    async def test_analyze_all_unavailable(self) -> None:
        runner = EngineRunner(engines=[MockEngine("test", available=False)])

        result = await runner.analyze("test")

        assert not result.success
        assert "No available engines" in result.errors

    @pytest.mark.asyncio
    async def test_analyze_engine_error_handled(self, segment: Segment) -> None:
        failing = MockEngine("failing")
        failing.analyze = AsyncMock(side_effect=Exception("Test error"))
        runner = EngineRunner(engines=[failing, MockEngine("working", [segment])])

        result = await runner.analyze("test")

        assert result.success
        assert result.primary_engine == "working"
        assert any("Test error" in e for e in result.errors)

    @pytest.mark.asyncio
    async def test_all_engines_failing_reports_errors(self) -> None:
        failing = MockEngine("failing")
        failing.analyze = AsyncMock(side_effect=Exception("Test error"))
        runner = EngineRunner(engines=[failing])

        result = await runner.analyze("test")

        assert not result.success
        assert any("Test error" in e for e in result.errors)

    def test_create_default(self) -> None:
        try:
            runner = EngineRunner.create_default()
        except ImportError:
            pytest.skip("Default engines not available")
        assert runner.engine_names == ["vidyut"]


class TestEngineFilter:
    """``engines=`` restricts a single call without mutating the shared list."""

    @pytest.mark.asyncio
    async def test_filter_leaves_engine_list_intact(self, segment: Segment) -> None:
        runner = EngineRunner(
            engines=[MockEngine("vidyut", [segment]), MockEngine("local_byt5", [segment])]
        )

        result = await runner.analyze("rAmaH", engines=["local_byt5"])

        assert set(result.engine_results) == {"local_byt5"}
        assert runner.engine_names == ["vidyut", "local_byt5"]

    @pytest.mark.asyncio
    async def test_filter_with_no_match_reports_error(self) -> None:
        runner = EngineRunner(engines=[MockEngine("vidyut", [])])

        result = await runner.analyze("rAmaH", engines=["nope"])

        assert result.errors == ["No engines configured"]


class TestAnalyzedSegment:
    """Tests for the AnalyzedSegment dataclass."""

    def test_from_segment_records_the_engine_vote(self) -> None:
        analyzed = AnalyzedSegment.from_segment(
            Segment(
                surface="test",
                lemma="lemma",
                morphology="noun",
                confidence=0.9,
                pos="noun",
                meanings=["meaning"],
            ),
            "vidyut",
        )

        assert analyzed.surface == "test"
        assert analyzed.lemma == "lemma"
        assert analyzed.morphology == "noun"
        assert analyzed.pos == "noun"
        assert analyzed.confidence == 0.9
        assert analyzed.meanings == ["meaning"]
        assert analyzed.engine_votes == {"vidyut": 0.9}
        assert analyzed.agreement_score == 1.0

    def test_from_segment_copies_meanings(self) -> None:
        """The analyzed segment must not alias the engine's own list."""
        source = Segment(surface="test", lemma="lemma", meanings=["meaning"])

        analyzed = AnalyzedSegment.from_segment(source, "vidyut")
        analyzed.meanings.append("added")

        assert source.meanings == ["meaning"]
