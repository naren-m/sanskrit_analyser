"""Tests for Vidyut engine wrapper."""

import pytest

from sanskrit_analyzer.engines.vidyut_engine import VidyutEngine


class TestVidyutEngine:
    """Tests for VidyutEngine class."""

    @pytest.fixture
    def engine(self) -> VidyutEngine:
        """Create a VidyutEngine instance."""
        return VidyutEngine()

    def test_engine_name(self, engine: VidyutEngine) -> None:
        """Test engine name property."""
        assert engine.name == "vidyut"

    def test_engine_weight(self, engine: VidyutEngine) -> None:
        """Test engine weight property."""
        assert engine.weight == 0.35

    @pytest.mark.asyncio
    async def test_analyze_simple_verb(self, engine: VidyutEngine) -> None:
        """Test analysis of a simple verb form."""
        if not engine.is_available:
            pytest.skip("Vidyut not available")

        result = await engine.analyze("gacCati")

        assert result.success
        assert result.engine == "vidyut"
        assert len(result.segments) >= 1

        # Check that we found the lemma 'gam'
        lemmas = [seg.lemma for seg in result.segments]
        assert "gam" in lemmas

    @pytest.mark.asyncio
    async def test_analyze_devanagari_input(self, engine: VidyutEngine) -> None:
        """Test analysis of Devanagari input."""
        if not engine.is_available:
            pytest.skip("Vidyut not available")

        result = await engine.analyze("गच्छति")

        assert result.success
        assert len(result.segments) >= 1

    @pytest.mark.asyncio
    async def test_analyze_iast_input(self, engine: VidyutEngine) -> None:
        """Test analysis of IAST input."""
        if not engine.is_available:
            pytest.skip("Vidyut not available")

        result = await engine.analyze("gacchati")

        assert result.success
        assert len(result.segments) >= 1

    @pytest.mark.asyncio
    async def test_analyze_compound(self, engine: VidyutEngine) -> None:
        """Test analysis of a compound word."""
        if not engine.is_available:
            pytest.skip("Vidyut not available")

        # rāmo gacchati = rāmaḥ + gacchati (with sandhi)
        result = await engine.analyze("rAmo gacCati")

        assert result.success
        assert len(result.segments) >= 2

    @pytest.mark.asyncio
    async def test_analyze_empty_input(self, engine: VidyutEngine) -> None:
        """Test analysis of empty input."""
        if not engine.is_available:
            pytest.skip("Vidyut not available")

        result = await engine.analyze("")

        # Empty input should not crash
        assert result.engine == "vidyut"

    @pytest.mark.asyncio
    async def test_confidence_returned(self, engine: VidyutEngine) -> None:
        """Test that confidence is returned."""
        if not engine.is_available:
            pytest.skip("Vidyut not available")

        result = await engine.analyze("gacCati")

        assert result.success
        assert result.confidence > 0
        for seg in result.segments:
            assert seg.confidence > 0
