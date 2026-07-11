"""Tests for Dharmamitra engine wrapper."""

from unittest.mock import MagicMock

import pytest

from sanskrit_analyzer.engines.dharmamitra_engine import DharmamitraEngine

# Deterministic offline stand-in for the Dharmamitra processor's response.
# Shape mirrors the live API: results[0]["grammatical_analysis"] is a list of
# per-word dicts with unsandhied/lemma/tag/meanings keys.
MOCK_PROCESSOR_RESULT = [
    {
        "grammatical_analysis": [
            {
                "unsandhied": "gacchati",
                "lemma": "gam",
                "tag": "Tense=Present, Mood=Indicative, Person=3, Number=Singular",
                "meanings": ["to go", "to move"],
            }
        ]
    }
]


class TestDharmamitraEngine:
    """Tests for DharmamitraEngine class."""

    @pytest.fixture
    def engine(self) -> DharmamitraEngine:
        """Create a DharmamitraEngine with a mocked (offline) processor.

        All ``analyze`` tests run against this mock so they are deterministic
        and never touch the live ``dharmamitra.org`` service.
        """
        engine = DharmamitraEngine()
        mock_processor = MagicMock()
        mock_processor.process_batch.return_value = MOCK_PROCESSOR_RESULT
        engine._processor = mock_processor
        engine._available = True
        return engine

    def test_engine_name(self, engine: DharmamitraEngine) -> None:
        """Test engine name property."""
        assert engine.name == "dharmamitra"

    def test_engine_weight(self, engine: DharmamitraEngine) -> None:
        """Test engine weight property."""
        assert engine.weight == 0.40

    def test_default_mode(self, engine: DharmamitraEngine) -> None:
        """Test default processing mode."""
        assert engine.mode == "unsandhied-lemma-morphosyntax"

    def test_set_mode(self, engine: DharmamitraEngine) -> None:
        """Test setting processing mode."""
        engine.mode = "lemma"
        assert engine.mode == "lemma"

    def test_set_invalid_mode_raises(self, engine: DharmamitraEngine) -> None:
        """Test that invalid mode raises ValueError."""
        with pytest.raises(ValueError):
            engine.mode = "invalid_mode"

    @pytest.mark.asyncio
    async def test_analyze_simple_verb(self, engine: DharmamitraEngine) -> None:
        """Test analysis of a simple verb form."""
        result = await engine.analyze("gacchati")

        assert result.success
        assert result.engine == "dharmamitra"
        assert len(result.segments) >= 1

        # Check that we found the lemma 'gam'
        lemmas = [seg.lemma for seg in result.segments]
        assert "gam" in lemmas

    @pytest.mark.asyncio
    async def test_analyze_with_meanings(self, engine: DharmamitraEngine) -> None:
        """Test that meanings are returned."""
        result = await engine.analyze("gacchati")

        assert result.success
        # At least one segment should have meanings
        meanings_found = any(len(seg.meanings) > 0 for seg in result.segments)
        assert meanings_found

    @pytest.mark.asyncio
    async def test_analyze_devanagari_input(self, engine: DharmamitraEngine) -> None:
        """Test analysis of Devanagari input."""
        result = await engine.analyze("गच्छति")

        assert result.success
        assert len(result.segments) >= 1

    @pytest.mark.asyncio
    async def test_analyze_slp1_input(self, engine: DharmamitraEngine) -> None:
        """Test analysis of SLP1 input."""
        result = await engine.analyze("gacCati")

        assert result.success
        assert len(result.segments) >= 1

    @pytest.mark.asyncio
    async def test_analyze_empty_input(self, engine: DharmamitraEngine) -> None:
        """Test analysis of empty input."""
        result = await engine.analyze("")

        # Empty input should not crash
        assert result.engine == "dharmamitra"
        assert len(result.segments) == 0

    @pytest.mark.asyncio
    async def test_morphology_tag_parsing(self, engine: DharmamitraEngine) -> None:
        """Test that morphology tags are parsed correctly."""
        result = await engine.analyze("gacchati")

        assert result.success
        for seg in result.segments:
            if seg.morphology:
                # Should contain verb-related tags
                assert "verb" in seg.morphology.lower() or len(seg.morphology) > 0

    @pytest.mark.asyncio
    async def test_confidence_returned(self, engine: DharmamitraEngine) -> None:
        """Test that confidence is returned."""
        result = await engine.analyze("gacchati")

        assert result.success
        assert result.confidence > 0
        for seg in result.segments:
            assert seg.confidence > 0

    @pytest.mark.asyncio
    async def test_processor_failure_handled_gracefully(
        self, engine: DharmamitraEngine
    ) -> None:
        """A 422/exception from the processor yields an unsuccessful result.

        The engine must not let a processor exception (e.g. the live API now
        returning HTTP 422) propagate; it should return an empty, unsuccessful
        EngineResult instead.
        """
        engine._processor.process_batch.side_effect = RuntimeError(
            "422 Client Error: Unprocessable Entity"
        )

        result = await engine.analyze("gacchati")

        assert not result.success
        assert result.segments == []
        assert result.confidence == 0.0
        assert result.error is not None
        assert "422" in result.error

    @pytest.mark.asyncio
    async def test_processor_empty_results_handled(
        self, engine: DharmamitraEngine
    ) -> None:
        """An empty result list from the processor is handled gracefully."""
        engine._processor.process_batch.return_value = []

        result = await engine.analyze("gacchati")

        assert not result.success
        assert result.segments == []
        assert result.error is not None


class TestDharmamitraEngineNetwork:
    """Live-network smoke test. Skipped by default (requires the public API)."""

    @pytest.mark.network
    @pytest.mark.skip(reason="Hits live dharmamitra.org API; run explicitly with -m network")
    @pytest.mark.asyncio
    async def test_analyze_real_network(self) -> None:
        """Analyze against the real Dharmamitra service (opt-in only)."""
        engine = DharmamitraEngine()
        if not engine.is_available:
            pytest.skip("Dharmamitra not available")

        result = await engine.analyze("gacchati")

        # Whatever the live API returns, the engine must not raise.
        assert result.engine == "dharmamitra"
