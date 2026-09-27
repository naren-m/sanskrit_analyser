"""Tests for ByT5SanskritEmbedder."""

import numpy as np
import pytest
import torch

from sanskrit_analyzer.embeddings.byt5_embedder import (
    _DEFAULT_D_MODEL,
    ByT5SanskritEmbedder,
    _masked_mean_pool,
)
from tests._cases import check_cases

# (id, hidden states, attention mask, expected pooled vectors)
POOL_CASES = [
    (
        "all tokens attended gives the plain mean",
        [[[1.0, 2.0], [3.0, 4.0], [5.0, 6.0]]],
        [[1, 1, 1]],
        [[3.0, 4.0]],
    ),
    (
        "masked positions are excluded",
        [[[1.0, 2.0], [3.0, 4.0], [100.0, 100.0]]],
        [[1, 1, 0]],
        [[2.0, 3.0]],
    ),
    (
        "short and long rows pool independently in one batch",
        [
            [[10.0, 10.0], [0.0, 0.0], [0.0, 0.0]],
            [[1.0, 1.0], [2.0, 2.0], [3.0, 3.0]],
        ],
        [[1, 0, 0], [1, 1, 1]],
        [[10.0, 10.0], [2.0, 2.0]],
    ),
]


def test_masked_mean_pool():
    def check(hidden, mask, expected):
        pooled = _masked_mean_pool(torch.tensor(hidden), torch.tensor(mask))
        torch.testing.assert_close(pooled, torch.tensor(expected), rtol=1e-6, atol=1e-6)

    check_cases(POOL_CASES, check)

    # An all-zero mask must not divide by zero.
    pooled = _masked_mean_pool(torch.tensor([[[1.0, 2.0]]]), torch.tensor([[0]]))
    assert torch.isfinite(pooled).all()


def test_lazy_construction_never_loads_the_model():
    embedder = ByT5SanskritEmbedder(model_name="google/byt5-small", lazy=True)
    assert embedder.device in {"mps", "cuda", "cpu"}

    # Empty input returns a (0, d) array without forcing a model load.
    vectors = embedder.encode([])
    assert vectors.shape == (0, _DEFAULT_D_MODEL)
    assert vectors.dtype == np.float32
    assert embedder._model is None


@pytest.mark.slow
def test_encode():
    embedder = ByT5SanskritEmbedder(model_name="google/byt5-small", device="cpu")
    # byt5-small has d_model=1472, read from the loaded config.
    assert embedder.embedding_dim == 1472

    vectors = embedder.encode(["रामो गच्छति", "सीता वनम् गता", "हनुमान् उड्डयते"])
    assert isinstance(vectors, np.ndarray)
    assert vectors.shape == (3, embedder.embedding_dim)
    assert np.isfinite(vectors).all()
    np.testing.assert_allclose(np.linalg.norm(vectors, axis=1), np.ones(3), rtol=1e-4, atol=1e-4)

    a, b = embedder.encode(["रामो गच्छति", "कोकिला कूजति"])
    cosine = float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))
    assert cosine < 0.9999

    empty = embedder.encode([])
    assert isinstance(empty, np.ndarray)
    assert empty.shape == (0, embedder.embedding_dim)
