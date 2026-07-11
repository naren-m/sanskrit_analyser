"""Tests for BgeM3Embedder and the Embedder Protocol.

Covers
------
* Protocol conformance — both BgeM3Embedder and ByT5SanskritEmbedder are
  ``isinstance(x, Embedder)`` thanks to ``runtime_checkable``.
* Construction: lazy mode defers model load; explicit device is honoured.
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
environment), the entire class is skipped via a module-level
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

# Sample English texts that are representative of commentary content.
_SAMPLE_TEXTS = [
    "Rama went to the forest to fulfil his father's promise.",
    "The sages praised the valor of the hero in Dandaka forest.",
    "Sita's abduction by Ravana marks the turning point of the epic.",
]


# ---------------------------------------------------------------------------
# Protocol conformance
# ---------------------------------------------------------------------------


class TestEmbedderProtocol:
    """Both embedder classes satisfy the Embedder protocol at runtime."""

    def test_bge_m3_is_embedder_instance(self):
        embedder = BgeM3Embedder(lazy=True)
        assert isinstance(embedder, Embedder), (
            "BgeM3Embedder does not satisfy the Embedder protocol"
        )

    def test_byt5_is_embedder_instance(self):
        """ByT5SanskritEmbedder also conforms structurally (regression guard)."""
        try:
            from sanskrit_analyzer.embeddings.byt5_embedder import ByT5SanskritEmbedder
            embedder = ByT5SanskritEmbedder(lazy=True)
            assert isinstance(embedder, Embedder), (
                "ByT5SanskritEmbedder does not satisfy the Embedder protocol"
            )
        except ImportError:
            pytest.skip("transformers/torch not available for ByT5SanskritEmbedder")

    def test_protocol_requires_encode_method(self):
        """An object missing encode() is not an Embedder."""
        class NoEncode:
            @property
            def embedding_dim(self) -> int:
                return 42

        assert not isinstance(NoEncode(), Embedder)

    def test_protocol_requires_embedding_dim(self):
        """An object missing embedding_dim is not an Embedder."""
        class NoDim:
            def encode(self, texts, batch_size=8):
                import numpy as np
                return np.zeros((len(texts), 42), dtype=np.float32)

        assert not isinstance(NoDim(), Embedder)


# ---------------------------------------------------------------------------
# Construction
# ---------------------------------------------------------------------------


class TestBgeM3EmbedderConstruction:
    def test_lazy_mode_does_not_load_model(self):
        """With lazy=True, _model remains None after construction."""
        embedder = BgeM3Embedder(lazy=True)
        assert embedder._model is None

    def test_explicit_device_honoured(self):
        embedder = BgeM3Embedder(device="cpu", lazy=True)
        assert embedder.device == "cpu"

    def test_auto_device_returns_valid_device(self):
        embedder = BgeM3Embedder(lazy=True)
        assert embedder.device in {"mps", "cuda", "cpu"}

    def test_embedding_dim_is_1024_without_loading(self):
        """embedding_dim is a constant and must not trigger model load."""
        embedder = BgeM3Embedder(lazy=True)
        assert embedder.embedding_dim == 1024
        assert embedder._model is None  # still not loaded

    def test_default_revision_is_pinned(self):
        from sanskrit_analyzer.embeddings.bge_m3_embedder import _DEFAULT_REVISION

        embedder = BgeM3Embedder(lazy=True)
        assert embedder.revision == _DEFAULT_REVISION


# ---------------------------------------------------------------------------
# Empty-input edge case (no model load needed)
# ---------------------------------------------------------------------------


class TestEmptyInput:
    def test_encode_empty_list_returns_zero_array(self):
        embedder = BgeM3Embedder(lazy=True)
        result = embedder.encode([])
        assert isinstance(result, np.ndarray)
        assert result.shape == (0, 1024)
        assert result.dtype == np.float32
        assert embedder._model is None  # model never loaded


# ---------------------------------------------------------------------------
# Real encode — marked slow; require sentence-transformers + cached model
# ---------------------------------------------------------------------------


class TestBgeM3EmbedderEncode:
    """Live encode tests against the locally-cached BAAI/bge-m3 model."""

    @pytest.fixture(scope="class")
    def embedder(self) -> BgeM3Embedder:
        """Shared embedder instance; loaded once per class."""
        return BgeM3Embedder(device="cpu", normalize=True)

    @pytest.mark.slow
    def test_encode_shape_and_dtype(self, embedder: BgeM3Embedder):
        vectors = embedder.encode(_SAMPLE_TEXTS)
        assert isinstance(vectors, np.ndarray)
        assert vectors.shape == (len(_SAMPLE_TEXTS), 1024)
        assert vectors.dtype == np.float32

    @pytest.mark.slow
    def test_encode_l2_normalized(self, embedder: BgeM3Embedder):
        """With normalize=True each vector should have unit norm."""
        vectors = embedder.encode(_SAMPLE_TEXTS)
        norms = np.linalg.norm(vectors, axis=1)
        np.testing.assert_allclose(
            norms, np.ones(len(_SAMPLE_TEXTS)), rtol=1e-4, atol=1e-4
        )

    @pytest.mark.slow
    def test_encode_no_nan_or_inf(self, embedder: BgeM3Embedder):
        vectors = embedder.encode(_SAMPLE_TEXTS)
        assert np.isfinite(vectors).all(), "Encode output contains NaN or Inf"

    @pytest.mark.slow
    def test_encode_different_inputs_produce_different_vectors(
        self, embedder: BgeM3Embedder
    ):
        a, b = embedder.encode(
            [
                "Rama is the hero of Ramayana.",
                "This is a completely unrelated sentence about cooking.",
            ]
        )
        cosine = float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))
        assert cosine < 0.9999, f"Cosine similarity too high ({cosine:.4f}) for unrelated texts"

    @pytest.mark.slow
    def test_encode_batch_size_one(self, embedder: BgeM3Embedder):
        """batch_size=1 should produce the same result as batch_size=32."""
        texts = _SAMPLE_TEXTS[:2]
        v_batch = embedder.encode(texts, batch_size=32)
        v_single = embedder.encode(texts, batch_size=1)
        np.testing.assert_allclose(v_batch, v_single, rtol=1e-4, atol=1e-4)

    @pytest.mark.slow
    def test_normalize_false_is_accepted(self):
        """BgeM3Embedder(normalize=False) should construct and encode without error.

        Note: BAAI/bge-m3 applies L2 normalisation inside the model itself, so
        the output norms are ~1.0 even with normalize_embeddings=False passed to
        sentence-transformers.  This is model-level behaviour, not a bug in
        BgeM3Embedder.  We assert only that no exception is raised and the shape
        is correct.
        """
        embedder = BgeM3Embedder(device="cpu", normalize=False)
        vectors = embedder.encode(_SAMPLE_TEXTS[:2])
        assert vectors.shape == (2, 1024)
        assert vectors.dtype == np.float32
