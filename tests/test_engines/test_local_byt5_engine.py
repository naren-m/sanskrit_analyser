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

    def test_parse_combined_compound_member_tokens(self) -> None:
        """Compound members come back as `__lemma_U` — lemma must not be dropped.

        For a compound like cittavṛttinirodhaḥ the model emits member tokens
        with an EMPTY surface slot: `__citta_U __vṛtti_U nirodhaḥ_nirodha_SNM`.
        Naive positional splitting yields surface='' lemma='' tags='citta',
        losing the lemma into the tags field (observed live, exp5 2026-07).
        """
        with patch.object(LocalByT5Engine, "_load_model"):
            engine = LocalByT5Engine(load_on_init=False)

            result = engine._parse_combined("__citta_U __vṛtti_U nirodhaḥ_nirodha_SNM")
            assert len(result) == 3
            assert result[0]["lemma"] == "citta"
            assert result[0]["surface"] == "citta"  # no surface given; fall back to lemma
            assert result[0]["tags"] == "U"
            assert result[1]["lemma"] == "vṛtti"
            assert result[1]["tags"] == "U"
            assert result[2]["surface"] == "nirodhaḥ"
            assert result[2]["lemma"] == "nirodha"
            assert result[2]["tags"] == "SNM"
            # no segment may end up with an empty lemma
            assert all(item["lemma"] for item in result)

    def test_parse_combined_empty_lemma_slot_falls_back_to_surface(self) -> None:
        """Token with an empty lemma slot (`surface__TAG`) uses surface as lemma."""
        with patch.object(LocalByT5Engine, "_load_model"):
            engine = LocalByT5Engine(load_on_init=False)

            result = engine._parse_combined("iti__Cp")
            assert len(result) == 1
            assert result[0]["surface"] == "iti"
            assert result[0]["lemma"] == "iti"
            assert result[0]["tags"] == "Cp"

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

    def test_normalize_to_iast_word_initial_slp1_capital(self) -> None:
        """SLP1 with a word-initial capital must reach the model as real IAST.

        The pipeline hands engines normalized SLP1. 'Bavati' (bhavati) has its
        only SLP1 marker at position 0, where the interior-capital heuristic
        cannot see it; misdetected as IAST it passed through unchanged and the
        model saw 'Bavati' -> lemma 'bav' instead of 'bhū' (observed live).
        """
        with patch.object(LocalByT5Engine, "_load_model"):
            engine = LocalByT5Engine(load_on_init=False)

            assert engine._normalize_to_iast("Bavati") == "bhavati"

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

    @pytest.mark.asyncio
    async def test_greedy_decode_splits_full_compound(
        self, skip_if_no_transformers: None
    ) -> None:
        """Greedy decoding must segment the whole compound, not truncate it.

        Regression for the beam-search + early_stopping bug that halted the beam
        at the first EOS and collapsed इक्ष्वाकुवंशप्रभवो to "ik". Runs offline
        against the cached model; skips if the model can't be loaded so CI
        without the weights still passes.
        """
        try:
            engine = LocalByT5Engine()
        except Exception as exc:  # model not cached / load failure
            pytest.skip(f"ByT5 model unavailable: {exc}")

        if not engine.is_available:
            pytest.skip("ByT5 model failed to load")

        verse = "इक्ष्वाकुवंशप्रभवो रामो नाम जनैः श्रुतः"
        output = engine._generate(engine._normalize_to_iast(verse), "S")
        members = engine._parse_segmentation(output)

        assert len(members) > 1, f"compound not split: {output!r}"
        joined = " ".join(members)
        assert "ikṣvāku" in joined, f"missing ikṣvāku in: {output!r}"
        assert "vaṃśa" in joined, f"missing vaṃśa in: {output!r}"
