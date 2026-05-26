"""Compose a frozen embedder with a trained projection head."""

from __future__ import annotations

from typing import Protocol

import numpy as np
import torch

from sanskrit_analyzer.embeddings.training.projection_head import (
    ProjectionHead,
)


class _EncoderLike(Protocol):
    @property
    def embedding_dim(self) -> int: ...
    def encode(self, texts: list[str], batch_size: int = ...) -> np.ndarray: ...


class AdaptedEmbedder:
    """Encoder + ProjectionHead behind the standard encode() interface.

    The encoder is consumed only via its public encode() method, so this
    class works with any object exposing encode(texts) -> np.ndarray and
    an embedding_dim property - not just ByT5SanskritEmbedder.
    """

    def __init__(self, embedder: _EncoderLike, head: ProjectionHead) -> None:
        if embedder.embedding_dim != head.input_dim:
            raise ValueError(
                f"Embedder dim {embedder.embedding_dim} does not match "
                f"head input_dim {head.input_dim}"
            )
        self._embedder = embedder
        self._head = head
        self._head.train(False)

    @property
    def embedding_dim(self) -> int:
        return self._head.output_dim

    def encode(self, texts: list[str], batch_size: int = 8) -> np.ndarray:
        if not texts:
            return np.zeros((0, self.embedding_dim), dtype=np.float32)
        raw = self._embedder.encode(texts, batch_size=batch_size)
        with torch.no_grad():
            t = torch.from_numpy(raw)
            projected = self._head(t).cpu().numpy()
        return projected.astype(np.float32)
