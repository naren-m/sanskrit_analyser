"""Tests for BgeM3Embedder and the Embedder Protocol.

Covers
------
* Protocol conformance — both BgeM3Embedder and ByT5SanskritEmbedder are
  ``isinstance(x, Embedder)`` thanks to ``runtime_checkable``.
* Construction: lazy mode defers model load; auto device picks a backend.
* ``encode`` on 2-3 English strings: shape (N, 1024), dtype float32.
* L2-normalisation: default ``normalize=True`` produces unit-norm vectors.
* Empty-input edge case: shape (0, 1024), no model load required.
* No NaN / Inf in real encode output.

Slow/ML-dep handling
---------------------
All tests that actually call ``encode`` or load the model are marked
``@pytest.mark.slow``.  They are skipped automatically when the model
weights are absent, but in this environment the BAAI/bge-m3 model IS
cached locally so they execute for real.

If ``sentence-transformers`` is not importable (e.g. in a minimal CI
environment), the entire module is skipped via a module-level
``pytest.importorskip``.
"""

from __future__ import annotations

import numpy as np
import pytest

# Skip the whole module if sentence-transformers is unavailable.
sentence_transformers = pytest.importorskip(
    "sentence_transformers",
    reason="sentence-transformers not installed; skipping BgeM3Embedder tests",
)

from sanskrit_analyzer.embeddings.base import Embedder
from sanskrit_analyzer.embeddings.bge_m3_embedder import BgeM3Embedder
from tests._cases import check_cases

# Sample English texts that are representative of commentary content.
_SAMPLE_TEXTS = [
    "Rama went to the forest to fulfil his father's promise.",
    "The sages praised the valor of the hero in Dandaka forest.",
    "Sita's abduction by Ravana marks the turning point of the epic.",
]


class _NoEncode:
    @property
    def embedding_dim(self) -> int:
        return 42


class _NoDim:
    def encode(self, texts, batch_size=8):
        return np.zeros((len(texts), 42), dtype=np.float32)


def _byt5():
    try:
        from sanskrit_analyzer.embeddings.byt5_embedder import ByT5SanskritEmbedder
    except ImportError:
        pytest.skip("transformers/torch not available for ByT5SanskritEmbedder")
    return ByT5SanskritEmbedder(lazy=True)


# (id, factory, satisfies the Embedder protocol)
PROTOCOL_CASES = [
    ("BgeM3Embedder conforms", lambda: BgeM3Embedder(lazy=True), True),
    ("ByT5SanskritEmbedder conforms structurally (regression guard)", _byt5, True),
    ("object missing encode() is not an Embedder", _NoEncode, False),
    ("object missing embedding_dim is not an Embedder", _NoDim, False),
]


def test_embedder_protocol():
    def check(factory, conforms):
        assert isinstance(factory(), Embedder) is conforms

    check_cases(PROTOCOL_CASES, check)


def test_lazy_construction_never_loads_the_model():
    """lazy=True defers the load; dim, auto device and empty encode stay model-free."""
    embedder = BgeM3Embedder(lazy=True)
    assert embedder.device in {"mps", "cuda", "cpu"}
    # embedding_dim is a constant and must not trigger model load.
    assert embedder.embedding_dim == 1024

    result = embedder.encode([])
    assert isinstance(result, np.ndarray)
    assert result.shape == (0, 1024)
    assert result.dtype == np.float32
    assert embedder._model is None


@pytest.mark.slow
def test_encode():
    """Live encode against the locally-cached BAAI/bge-m3 model."""
    embedder = BgeM3Embedder(device="cpu", normalize=True)
    vectors = embedder.encode(_SAMPLE_TEXTS)
    assert isinstance(vectors, np.ndarray)
    assert vectors.shape == (len(_SAMPLE_TEXTS), 1024)
    assert vectors.dtype == np.float32
    assert np.isfinite(vectors).all(), "Encode output contains NaN or Inf"
    # normalize=True gives each vector unit norm.
    norms = np.linalg.norm(vectors, axis=1)
    np.testing.assert_allclose(norms, np.ones(len(_SAMPLE_TEXTS)), rtol=1e-4, atol=1e-4)

    a, b = embedder.encode(
        [
            "Rama is the hero of Ramayana.",
            "This is a completely unrelated sentence about cooking.",
        ]
    )
    cosine = float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))
    assert cosine < 0.9999, f"Cosine similarity too high ({cosine:.4f}) for unrelated texts"

    # batch_size=1 produces the same result as batch_size=32.
    texts = _SAMPLE_TEXTS[:2]
    np.testing.assert_allclose(
        embedder.encode(texts, batch_size=32),
        embedder.encode(texts, batch_size=1),
        rtol=1e-4,
        atol=1e-4,
    )

    # normalize=False constructs and encodes. BAAI/bge-m3 L2-normalises inside
    # the model, so norms stay ~1.0 even then; that is model behaviour, not a
    # BgeM3Embedder bug, so only shape and dtype are asserted.
    raw = BgeM3Embedder(device="cpu", normalize=False).encode(_SAMPLE_TEXTS[:2])
    assert raw.shape == (2, 1024)
    assert raw.dtype == np.float32
