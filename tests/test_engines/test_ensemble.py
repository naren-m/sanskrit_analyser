"""Tests for ensemble analyzer."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from sanskrit_analyzer.engines.base import EngineBase, EngineResult, Segment
from sanskrit_analyzer.engines.ensemble import (
    EnsembleAnalyzer,
    EnsembleConfig,
    MergedSegment,
)


class MockEngine(EngineBase):
    """Mock engine for testing."""

    def __init__(
        self,
        name: str,
        weight: float = 0.33,
        segments: list[Segment] | None = None,
        available: bool = True,
    ) -> None:
        self._name = name
        self._weight = weight
        self._segments = segments or []
        self._available = available

    @property
    def name(self) -> str:
        return self._name

    @property
    def weight(self) -> float:
        return self._weight

    @property
    def is_available(self) -> bool:
        return self._available

    async def analyze(self, text: str) -> EngineResult:
        return EngineResult(
            engine=self._name,
            segments=self._segments,
            confidence=0.9 if self._segments else 0.0,
        )


class TestEnsembleAnalyzer:
    """Tests for EnsembleAnalyzer class."""

    @pytest.fixture
    def config(self) -> EnsembleConfig:
        """Create ensemble config."""
        return EnsembleConfig()

    @pytest.fixture
    def mock_engines(self) -> list[MockEngine]:
        """Create mock engines with agreeing results."""
        segment = Segment(surface="gacchati", lemma="gam", confidence=0.9)
        return [
            MockEngine("vidyut", 0.35, [segment]),
            MockEngine("dharmamitra", 0.40, [segment]),
            MockEngine("heritage", 0.25, [segment]),
        ]

    def test_add_engine(self, config: EnsembleConfig) -> None:
        """Test adding engines."""
        analyzer = EnsembleAnalyzer(config=config)
        engine = MockEngine("test", 0.5)

        analyzer.add_engine(engine)

        assert "test" in analyzer.engine_names

    def test_remove_engine(self, mock_engines: list[MockEngine]) -> None:
        """Test removing engines."""
        analyzer = EnsembleAnalyzer(engines=mock_engines)

        analyzer.remove_engine("vidyut")

        assert "vidyut" not in analyzer.engine_names
        assert len(analyzer.engine_names) == 2

    def test_available_engines(self) -> None:
        """Test available engines property."""
        engines = [
            MockEngine("available", available=True),
            MockEngine("unavailable", available=False),
        ]
        analyzer = EnsembleAnalyzer(engines=engines)

        assert "available" in analyzer.available_engines
        assert "unavailable" not in analyzer.available_engines

    @pytest.mark.asyncio
    async def test_analyze_all_agree(
        self, mock_engines: list[MockEngine]
    ) -> None:
        """Test analysis when all engines agree."""
        analyzer = EnsembleAnalyzer(engines=mock_engines)

        result = await analyzer.analyze("gacchati")

        assert result.success
        assert len(result.segments) == 1
        assert result.segments[0].lemma == "gam"
        assert result.agreement_level == "high"
        assert len(result.available_engines) == 3

    @pytest.mark.asyncio
    async def test_analyze_partial_agreement(self) -> None:
        """Test analysis when engines partially agree."""
        engines = [
            MockEngine(
                "engine1", 0.33, [Segment(surface="test", lemma="lemma1", confidence=0.9)]
            ),
            MockEngine(
                "engine2", 0.33, [Segment(surface="test", lemma="lemma1", confidence=0.9)]
            ),
            MockEngine(
                "engine3", 0.33, [Segment(surface="test", lemma="lemma2", confidence=0.9)]
            ),
        ]
        analyzer = EnsembleAnalyzer(engines=engines)

        result = await analyzer.analyze("test")

        assert result.success
        # Most common lemma should win
        assert result.segments[0].lemma == "lemma1"

    @pytest.mark.asyncio
    async def test_analyze_no_engines(self) -> None:
        """Test analysis with no engines."""
        analyzer = EnsembleAnalyzer(engines=[])

        result = await analyzer.analyze("test")

        assert not result.success
        assert "No engines configured" in result.errors

    @pytest.mark.asyncio
    async def test_analyze_all_unavailable(self) -> None:
        """Test analysis when all engines are unavailable."""
        engines = [
            MockEngine("test", available=False),
        ]
        analyzer = EnsembleAnalyzer(engines=engines)

        result = await analyzer.analyze("test")

        assert not result.success
        assert "No available engines" in result.errors

    @pytest.mark.asyncio
    async def test_analyze_engine_error_handled(self) -> None:
        """Test that engine errors are handled gracefully."""
        # Create engine that raises exception
        failing_engine = MockEngine("failing")
        failing_engine.analyze = AsyncMock(side_effect=Exception("Test error"))

        working_engine = MockEngine(
            "working", segments=[Segment(surface="test", lemma="test", confidence=0.9)]
        )

        analyzer = EnsembleAnalyzer(engines=[failing_engine, working_engine])

        result = await analyzer.analyze("test")

        # Should still get result from working engine
        assert result.success
        assert len(result.segments) == 1

    @pytest.mark.asyncio
    async def test_analyze_merges_meanings(self) -> None:
        """Test that meanings from all engines are merged."""
        engines = [
            MockEngine(
                "engine1",
                0.5,
                [Segment(surface="test", lemma="test", meanings=["meaning1"])],
            ),
            MockEngine(
                "engine2",
                0.5,
                [Segment(surface="test", lemma="test", meanings=["meaning2"])],
            ),
        ]
        analyzer = EnsembleAnalyzer(engines=engines)

        result = await analyzer.analyze("test")

        assert result.success
        meanings = result.segments[0].meanings
        assert "meaning1" in meanings
        assert "meaning2" in meanings

    @pytest.mark.asyncio
    async def test_analyze_weighted_confidence(self) -> None:
        """Test that confidence is weighted by engine weights."""
        # Higher weight engine with high confidence
        engines = [
            MockEngine(
                "high_weight",
                0.7,
                [Segment(surface="test", lemma="test", confidence=0.9)],
            ),
            MockEngine(
                "low_weight",
                0.3,
                [Segment(surface="test", lemma="test", confidence=0.5)],
            ),
        ]
        analyzer = EnsembleAnalyzer(engines=engines)
        analyzer._weights = {"high_weight": 0.7, "low_weight": 0.3}

        result = await analyzer.analyze("test")

        assert result.success
        # Confidence should be weighted toward high_weight engine
        assert result.segments[0].confidence > 0.7

    def test_create_default(self) -> None:
        """Test creating default ensemble."""
        # This tests the factory method
        try:
            analyzer = EnsembleAnalyzer.create_default()
            assert len(analyzer.engine_names) == 3
            assert "vidyut" in analyzer.engine_names
            assert "dharmamitra" in analyzer.engine_names
            assert "heritage" in analyzer.engine_names
        except ImportError:
            pytest.skip("Default engines not available")


class TestMergedSegment:
    """Tests for MergedSegment dataclass."""

    def test_to_segment(self) -> None:
        """Test conversion to base Segment."""
        merged = MergedSegment(
            surface="test",
            lemma="lemma",
            morphology="noun",
            confidence=0.9,
            pos="noun",
            meanings=["meaning"],
            engine_votes={"engine1": 0.9},
            agreement_score=1.0,
        )

        segment = merged.to_segment()

        assert segment.surface == "test"
        assert segment.lemma == "lemma"
        assert segment.confidence == 0.9
