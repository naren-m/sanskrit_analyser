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
