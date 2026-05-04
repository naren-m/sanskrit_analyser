"""Tests for AdaptedEmbedder."""

import numpy as np
import pytest
import torch

from sanskrit_analyzer.embeddings.training.adapted_embedder import (
    AdaptedEmbedder,
)
from sanskrit_analyzer.embeddings.training.projection_head import (
    ProjectionHead,
)


class _StubEmbedder:
    """Mimics ByT5SanskritEmbedder without loading a real model."""

    def __init__(self, dim: int = 16):
        self._dim = dim

    @property
    def embedding_dim(self) -> int:
        return self._dim

    def encode(self, texts: list[str], batch_size: int = 8) -> np.ndarray:
        if not texts:
            return np.zeros((0, self._dim), dtype=np.float32)
        rng = np.random.default_rng(seed=len(texts))
        return rng.standard_normal((len(texts), self._dim)).astype(np.float32)


class TestAdaptedEmbedder:
    def test_encode_returns_projected_dimension(self):
        embedder = _StubEmbedder(dim=16)
        head = ProjectionHead(input_dim=16, hidden_dim=8, output_dim=4)
        adapted = AdaptedEmbedder(embedder, head)

        out = adapted.encode(["a", "b", "c"])
        assert isinstance(out, np.ndarray)
        assert out.shape == (3, 4)
        assert adapted.embedding_dim == 4

    def test_empty_input_returns_empty_array(self):
        embedder = _StubEmbedder(dim=16)
        head = ProjectionHead(input_dim=16, hidden_dim=8, output_dim=4)
        adapted = AdaptedEmbedder(embedder, head)

        out = adapted.encode([])
        assert out.shape == (0, 4)

    def test_output_is_l2_normalized_when_head_normalizes(self):
        embedder = _StubEmbedder(dim=16)
        head = ProjectionHead(
            input_dim=16, hidden_dim=8, output_dim=4, normalize=True
        )
        adapted = AdaptedEmbedder(embedder, head)

        out = adapted.encode(["x", "y"])
        norms = np.linalg.norm(out, axis=1)
        np.testing.assert_allclose(norms, np.ones(2), rtol=1e-4, atol=1e-4)

    def test_dim_mismatch_raises(self):
        embedder = _StubEmbedder(dim=16)
        head = ProjectionHead(input_dim=8, hidden_dim=8, output_dim=4)
        with pytest.raises(ValueError, match="does not match"):
            AdaptedEmbedder(embedder, head)
