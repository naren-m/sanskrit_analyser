"""Tests for ByT5SanskritEmbedder."""

import numpy as np
import pytest
import torch

from sanskrit_analyzer.embeddings.byt5_embedder import (
    ByT5SanskritEmbedder,
    _masked_mean_pool,
)


class TestMaskedMeanPool:
    def test_all_tokens_attended_gives_plain_mean(self):
        hidden = torch.tensor([[[1.0, 2.0], [3.0, 4.0], [5.0, 6.0]]])
        mask = torch.tensor([[1, 1, 1]])
        pooled = _masked_mean_pool(hidden, mask)
        assert pooled.shape == (1, 2)
        torch.testing.assert_close(
            pooled, torch.tensor([[3.0, 4.0]]), rtol=1e-6, atol=1e-6
        )

    def test_masked_positions_excluded(self):
        hidden = torch.tensor([[[1.0, 2.0], [3.0, 4.0], [100.0, 100.0]]])
        mask = torch.tensor([[1, 1, 0]])
        pooled = _masked_mean_pool(hidden, mask)
        torch.testing.assert_close(
            pooled, torch.tensor([[2.0, 3.0]]), rtol=1e-6, atol=1e-6
        )

    def test_short_and_long_in_same_batch(self):
        hidden = torch.tensor([
            [[10.0, 10.0], [0.0, 0.0], [0.0, 0.0]],
            [[1.0, 1.0], [2.0, 2.0], [3.0, 3.0]],
        ])
        mask = torch.tensor([[1, 0, 0], [1, 1, 1]])
        pooled = _masked_mean_pool(hidden, mask)
        torch.testing.assert_close(
            pooled,
            torch.tensor([[10.0, 10.0], [2.0, 2.0]]),
            rtol=1e-6,
            atol=1e-6,
        )

    def test_empty_mask_does_not_divide_by_zero(self):
        hidden = torch.tensor([[[1.0, 2.0]]])
        mask = torch.tensor([[0]])
        pooled = _masked_mean_pool(hidden, mask)
        assert torch.isfinite(pooled).all()


class TestByT5SanskritEmbedderConstruction:
    def test_explicit_device_is_honored(self):
        embedder = ByT5SanskritEmbedder(
            model_name="google/byt5-small", device="cpu", lazy=True
        )
        assert embedder.device == "cpu"

    def test_auto_device_selects_available_backend(self):
        embedder = ByT5SanskritEmbedder(
            model_name="google/byt5-small", lazy=True
        )
        assert embedder.device in {"mps", "cuda", "cpu"}

    @pytest.mark.slow
    def test_embedding_dim_available_after_load(self):
        embedder = ByT5SanskritEmbedder(
            model_name="google/byt5-small", device="cpu"
        )
        # byt5-small has d_model=1472
        assert embedder.embedding_dim == 1472


class TestByT5SanskritEmbedderEncode:
    @pytest.fixture(scope="class")
    def embedder(self) -> ByT5SanskritEmbedder:
        return ByT5SanskritEmbedder(
            model_name="google/byt5-small", device="cpu"
        )

    @pytest.mark.slow
    def test_encode_returns_expected_shape(self, embedder):
        texts = ["रामो गच्छति", "सीता वनम् गता", "हनुमान् उड्डयते"]
        vectors = embedder.encode(texts)
        assert isinstance(vectors, np.ndarray)
        assert vectors.shape == (3, embedder.embedding_dim)

    @pytest.mark.slow
    def test_encode_different_inputs_produce_different_vectors(self, embedder):
        a, b = embedder.encode(["रामो गच्छति", "कोकिला कूजति"])
        cosine = float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))
        assert cosine < 0.9999

    @pytest.mark.slow
    def test_encode_normalization(self, embedder):
        vectors = embedder.encode(["रामो गच्छति", "सीता वनम् गता"])
        norms = np.linalg.norm(vectors, axis=1)
        np.testing.assert_allclose(norms, np.ones(2), rtol=1e-4, atol=1e-4)

    def test_encode_empty_list_returns_empty_array(self, embedder):
        vectors = embedder.encode([])
        assert isinstance(vectors, np.ndarray)
        assert vectors.shape == (0, embedder.embedding_dim)

    @pytest.mark.slow
    def test_encode_no_nan_or_inf(self, embedder):
        vectors = embedder.encode(["रामो गच्छति"])
        assert np.isfinite(vectors).all()
