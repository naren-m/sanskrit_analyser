"""BGE-M3 dense embedder via sentence-transformers.

Uses ``BAAI/bge-m3`` (1024-dimensional, multilingual) for encoding English
commentary chunks.  Only the dense CLS-pooled vectors are produced; BGE-M3
also supports sparse lexical and ColBERT multi-vector outputs, but those are
omitted here because the downstream Qdrant collection is configured as a
dense-only index.  Adding sparse/ColBERT support would require switching to
the FlagEmbedding library; document in a future task if needed.

Model is loaded lazily on first ``encode()`` call.  Weights are read from the
local Hugging Face cache (``~/.cache/huggingface/hub/models--BAAI--bge-m3``);
no network access is required once the cache is populated.
"""

from __future__ import annotations

import logging
from typing import Optional

import numpy as np

logger = logging.getLogger(__name__)

_DEFAULT_MODEL = "BAAI/bge-m3"
_EMBEDDING_DIM = 1024


def _auto_device() -> str:
    """Pick the best available torch backend (mirrors ByT5SanskritEmbedder)."""
    try:
        import torch

        if torch.backends.mps.is_available():
            return "mps"
        if torch.cuda.is_available():
            return "cuda"
    except ImportError:
        pass
    return "cpu"


class BgeM3Embedder:
    """Dense-vector embedder backed by ``BAAI/bge-m3``.

    Conforms to the :class:`~.base.Embedder` protocol structurally.

    Parameters
    ----------
    model_name:
        Hugging Face model identifier.  Defaults to ``"BAAI/bge-m3"``.
    device:
        ``"cpu"``, ``"cuda"``, ``"mps"``, or ``None`` (auto-detect).
    normalize:
        When ``True`` (default), output vectors are L2-normalised to unit
        length — required for cosine-similarity search in Qdrant.
    lazy:
        When ``True``, defer model loading until the first ``encode()`` call.
        Useful in test environments to avoid loading the model at construction
        time.
    """

    def __init__(
        self,
        model_name: str = _DEFAULT_MODEL,
        device: Optional[str] = None,
        normalize: bool = True,
        lazy: bool = False,
    ) -> None:
        self.model_name = model_name
        self.device = device or _auto_device()
        self.normalize = normalize
        self._model = None  # SentenceTransformer, loaded on demand
        if not lazy:
            self._load()

    # ------------------------------------------------------------------
    # Embedder protocol
    # ------------------------------------------------------------------

    @property
    def embedding_dim(self) -> int:
        """Return the output dimension (1024 for BAAI/bge-m3)."""
        return _EMBEDDING_DIM

    def encode(self, texts: list[str], batch_size: int = 32) -> np.ndarray:
        """Encode *texts* into dense float32 vectors of shape ``(N, 1024)``.

        Empty input returns a ``(0, 1024)`` array immediately without loading
        the model.
        """
        if len(texts) == 0:
            return np.zeros((0, self.embedding_dim), dtype=np.float32)

        if self._model is None:
            self._load()

        vectors = self._model.encode(
            texts,
            batch_size=batch_size,
            normalize_embeddings=self.normalize,
            convert_to_numpy=True,
            show_progress_bar=False,
        )
        return vectors.astype(np.float32)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _load(self) -> None:
        if self._model is not None:
            return
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as exc:
            raise ImportError(
                "sentence-transformers is required for BgeM3Embedder. "
                "Install it with: pip install 'sentence-transformers>=2.7'"
            ) from exc

        logger.info("Loading %s on %s", self.model_name, self.device)
        self._model = SentenceTransformer(
            self.model_name,
            device=self.device,
        )
        self._model.eval()
