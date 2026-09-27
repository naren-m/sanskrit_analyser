"""Tests for AdaptedEmbedder."""

import numpy as np
import pytest

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


def test_encode_projects_through_the_head():
    head = ProjectionHead(input_dim=16, hidden_dim=8, output_dim=4, normalize=True)
    adapted = AdaptedEmbedder(_StubEmbedder(dim=16), head)
    assert adapted.embedding_dim == 4

    out = adapted.encode(["a", "b", "c"])
    assert isinstance(out, np.ndarray)
    assert out.shape == (3, 4)
    # The head normalizes, so the adapted output is unit-norm.
    np.testing.assert_allclose(np.linalg.norm(out, axis=1), np.ones(3), rtol=1e-4, atol=1e-4)

    assert adapted.encode([]).shape == (0, 4)


def test_dim_mismatch_raises():
    head = ProjectionHead(input_dim=8, hidden_dim=8, output_dim=4)
    with pytest.raises(ValueError, match="does not match"):
        AdaptedEmbedder(_StubEmbedder(dim=16), head)
