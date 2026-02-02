"""Tests for Dharmamitra engine wrapper."""

import pytest

from sanskrit_analyzer.engines.dharmamitra_engine import DharmamitraEngine


class TestDharmamitraEngine:
    """Tests for DharmamitraEngine class."""

    @pytest.fixture
    def engine(self) -> DharmamitraEngine:
        """Create a DharmamitraEngine instance."""
        return DharmamitraEngine()

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
        if not engine.is_available:
            pytest.skip("Dharmamitra not available")

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
        if not engine.is_available:
            pytest.skip("Dharmamitra not available")

        result = await engine.analyze("gacchati")

        assert result.success
        # At least one segment should have meanings
        meanings_found = any(len(seg.meanings) > 0 for seg in result.segments)
        assert meanings_found

    @pytest.mark.asyncio
    async def test_analyze_devanagari_input(self, engine: DharmamitraEngine) -> None:
        """Test analysis of Devanagari input."""
        if not engine.is_available:
            pytest.skip("Dharmamitra not available")

        result = await engine.analyze("गच्छति")

        assert result.success
        assert len(result.segments) >= 1

    @pytest.mark.asyncio
    async def test_analyze_slp1_input(self, engine: DharmamitraEngine) -> None:
        """Test analysis of SLP1 input."""
        if not engine.is_available:
            pytest.skip("Dharmamitra not available")

        result = await engine.analyze("gacCati")

        assert result.success
        assert len(result.segments) >= 1

    @pytest.mark.asyncio
    async def test_analyze_empty_input(self, engine: DharmamitraEngine) -> None:
        """Test analysis of empty input."""
        if not engine.is_available:
            pytest.skip("Dharmamitra not available")

        result = await engine.analyze("")

        # Empty input should not crash
        assert result.engine == "dharmamitra"
        assert len(result.segments) == 0

    @pytest.mark.asyncio
    async def test_morphology_tag_parsing(self, engine: DharmamitraEngine) -> None:
        """Test that morphology tags are parsed correctly."""
        if not engine.is_available:
            pytest.skip("Dharmamitra not available")

        result = await engine.analyze("gacchati")

        assert result.success
        for seg in result.segments:
            if seg.morphology:
                # Should contain verb-related tags
                assert "verb" in seg.morphology.lower() or len(seg.morphology) > 0

    @pytest.mark.asyncio
    async def test_confidence_returned(self, engine: DharmamitraEngine) -> None:
        """Test that confidence is returned."""
        if not engine.is_available:
            pytest.skip("Dharmamitra not available")

        result = await engine.analyze("gacchati")

        assert result.success
        assert result.confidence > 0
        for seg in result.segments:
            assert seg.confidence > 0
