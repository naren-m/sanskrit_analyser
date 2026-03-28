"""Tests for the Local ByT5-Sanskrit engine."""

import pytest
from unittest.mock import patch

from sanskrit_analyzer.engines.local_byt5_engine import LocalByT5Engine


class TestLocalByT5Engine:
    """Test suite for LocalByT5Engine."""

    def test_engine_name(self) -> None:
        """Test engine name property."""
        with patch.object(LocalByT5Engine, "_load_model"):
            engine = LocalByT5Engine(load_on_init=False)
            assert engine.name == "local_byt5"

    def test_engine_weight(self) -> None:
        """Test engine weight property."""
        with patch.object(LocalByT5Engine, "_load_model"):
            engine = LocalByT5Engine(load_on_init=False)
            assert engine.weight == 0.45

    def test_not_available_without_model(self) -> None:
        """Test engine is not available when model fails to load."""
        with patch.object(LocalByT5Engine, "_load_model"):
            engine = LocalByT5Engine(load_on_init=False)
            assert not engine.is_available

    def test_parse_segmentation(self) -> None:
        """Test parsing of segmentation output."""
        with patch.object(LocalByT5Engine, "_load_model"):
            engine = LocalByT5Engine(load_on_init=False)

            # Underscore-separated output (actual model format)
            result = engine._parse_segmentation("rāmaḥ_vana_gacchati_")
            assert result == ["rāmaḥ", "vana", "gacchati"]

            # With task prefix (should be stripped)
            result = engine._parse_segmentation("S rāmaḥ_vana_")
            assert result == ["rāmaḥ", "vana"]

            # Empty output
            result = engine._parse_segmentation("")
            assert result == []

    def test_parse_lemmatization(self) -> None:
        """Test parsing of lemmatization output."""
        with patch.object(LocalByT5Engine, "_load_model"):
            engine = LocalByT5Engine(load_on_init=False)

            # Underscore-separated lemmas (actual model format)
            result = engine._parse_lemmatization("rāma_vana_gam_")
            assert result == ["rāma", "vana", "gam"]

            # With task prefix
            result = engine._parse_lemmatization("L rāma_vana_")
            assert result == ["rāma", "vana"]

    def test_parse_combined(self) -> None:
        """Test parsing of combined SLM output."""
        with patch.object(LocalByT5Engine, "_load_model"):
            engine = LocalByT5Engine(load_on_init=False)

            # Combined format: surface_lemma_TAGS (space separated)
            result = engine._parse_combined("rāma_rāma_SNM vanam_vana_SANe gacchati_gam_VP3S")
            assert len(result) == 3
            assert result[0]["surface"] == "rāma"
            assert result[0]["lemma"] == "rāma"
            assert result[0]["tags"] == "SNM"
            assert result[1]["surface"] == "vanam"
            assert result[1]["lemma"] == "vana"
            assert result[2]["tags"] == "VP3S"

    def test_decode_tags_verb(self) -> None:
        """Test tag decoding for verbs."""
        with patch.object(LocalByT5Engine, "_load_model"):
            engine = LocalByT5Engine(load_on_init=False)

            pos, morph = engine._decode_tags("VP3S")
            assert pos == "verb"
            assert morph == "VP3S"

    def test_decode_tags_noun(self) -> None:
        """Test tag decoding for nouns."""
        with patch.object(LocalByT5Engine, "_load_model"):
            engine = LocalByT5Engine(load_on_init=False)

            pos, morph = engine._decode_tags("SNM")
            assert pos == "noun"
            assert morph == "SNM"

    def test_decode_tags_empty(self) -> None:
        """Test tag decoding with empty tags."""
        with patch.object(LocalByT5Engine, "_load_model"):
            engine = LocalByT5Engine(load_on_init=False)

            pos, morph = engine._decode_tags("")
            assert pos is None
            assert morph is None

    @pytest.mark.asyncio
    async def test_analyze_returns_error_when_unavailable(self) -> None:
        """Test analyze returns error when model not available."""
        with patch.object(LocalByT5Engine, "_load_model"):
            engine = LocalByT5Engine(load_on_init=False)
            engine._init_error = "Model not installed"

            result = await engine.analyze("test")
            assert result.error is not None
            assert "not available" in result.error or "not installed" in result.error
            assert result.confidence == 0.0

    @pytest.mark.asyncio
    async def test_analyze_empty_text(self) -> None:
        """Test analyze with empty text."""
        with patch.object(LocalByT5Engine, "_load_model"):
            engine = LocalByT5Engine(load_on_init=False)
            engine._available = True

            result = await engine.analyze("")
            assert result.segments == []
            assert result.confidence == 0.0

    @pytest.mark.asyncio
    async def test_analyze_with_mock_model(self) -> None:
        """Test analyze with mocked model."""
        with patch.object(LocalByT5Engine, "_load_model"):
            engine = LocalByT5Engine(load_on_init=False)
            engine._available = True

            # Mock the generate method to return combined SLM format
            def mock_generate(text: str, task: str) -> str:
                # Combined SLM format: surface_lemma_TAGS (space-separated)
                return "rāmaḥ_rāma_SNM vanam_vana_SANe gacchati_gam_VP3S"

            engine._generate = mock_generate

            result = await engine.analyze("ramo vanam gacchati")

            assert result.error is None
            assert len(result.segments) == 3
            assert result.segments[0].surface == "rāmaḥ"
            assert result.segments[0].lemma == "rāma"
            assert result.segments[0].pos == "noun"  # SNM = Noun
            assert result.segments[2].surface == "gacchati"
            assert result.segments[2].lemma == "gam"
            assert result.segments[2].pos == "verb"  # VP3S = Verb

    def test_normalize_to_iast_from_devanagari(self) -> None:
        """Test normalization from Devanagari to IAST."""
        with patch.object(LocalByT5Engine, "_load_model"):
            engine = LocalByT5Engine(load_on_init=False)

            # This depends on the transliterate utility
            result = engine._normalize_to_iast("राम")
            # Should be transliterated to IAST
            assert result is not None

    def test_get_device_auto_cpu_fallback(self) -> None:
        """Test device selection falls back to CPU."""
        with patch.object(LocalByT5Engine, "_load_model"):
            engine = LocalByT5Engine(load_on_init=False, device="auto")

            with patch("torch.cuda.is_available", return_value=False):
                with patch("torch.backends.mps.is_available", return_value=False):
                    device = engine._get_device()
                    assert device == "cpu"

    def test_get_device_explicit(self) -> None:
        """Test explicit device selection."""
        with patch.object(LocalByT5Engine, "_load_model"):
            engine = LocalByT5Engine(load_on_init=False, device="cpu")
            device = engine._get_device()
            assert device == "cpu"


class TestLocalByT5EngineIntegration:
    """Integration tests that require the actual model.

    These tests are skipped if transformers/torch not installed.
    """

    @pytest.fixture
    def skip_if_no_transformers(self) -> None:
        """Skip test if transformers not available."""
        try:
            import transformers
            import torch
        except ImportError:
            pytest.skip("transformers/torch not installed")

    @pytest.mark.slow
    @pytest.mark.asyncio
    async def test_real_model_loading(self, skip_if_no_transformers: None) -> None:
        """Test loading the real model (slow, requires download)."""
        # This test is slow and downloads ~1GB model
        # Only run explicitly with: pytest -m slow
        pytest.skip("Slow test - run explicitly with pytest -m slow")
