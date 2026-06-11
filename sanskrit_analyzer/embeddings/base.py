"""Embedder Protocol for all sentence embedding backends.

Any class that implements ``encode(texts, batch_size) -> np.ndarray`` and
exposes ``embedding_dim: int`` conforms structurally, without needing to
inherit from this class.

Existing conforming implementations
------------------------------------
* :class:`~.byt5_embedder.ByT5SanskritEmbedder` — ByT5 encoder with
  masked mean pooling (1472-dim for byt5-small, 1536 for byt5-base).
* :class:`~.bge_m3_embedder.BgeM3Embedder` — BAAI/bge-m3 dense vectors
  via ``sentence-transformers`` (1024-dim, L2-normalized by default).
"""

from __future__ import annotations

from typing import runtime_checkable

import numpy as np

try:
    from typing import Protocol
except ImportError:  # Python 3.7 compat (not used here, just defensive)
    from typing_extensions import Protocol  # type: ignore[assignment]


@runtime_checkable
class Embedder(Protocol):
    """Minimal protocol for dense text embedders.

    Implementers are not required to inherit from this class — structural
    subtyping (duck typing) is sufficient thanks to ``runtime_checkable``.

    Parameters accepted by ``encode``
    -----------------------------------
    texts:
        List of plain-text strings to encode.  May contain Sanskrit in
        Devanagari or IAST, English, or mixed.
    batch_size:
        Number of texts processed in a single forward pass.  Lower values
        reduce peak GPU/CPU memory; higher values improve throughput.

    Returns
    -------
    ``np.ndarray`` of shape ``(len(texts), embedding_dim)``, dtype float32.
    Empty input returns shape ``(0, embedding_dim)``.
    """

    def encode(self, texts: list[str], batch_size: int = 8) -> np.ndarray:
        """Encode *texts* into dense float32 vectors."""
        ...

    @property
    def embedding_dim(self) -> int:
        """Number of dimensions in each output vector."""
        ...
