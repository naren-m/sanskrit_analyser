"""ByT5-based Sanskrit embedder using encoder mean pooling.

See docs/superpowers/specs/2026-04-18-byt5-sanskrit-embeddings-design.md
in the ramayanam repo for the design rationale.
"""

from __future__ import annotations

import logging
from typing import Optional

import torch
from transformers import ByT5Tokenizer, T5ForConditionalGeneration

logger = logging.getLogger(__name__)

_DEFAULT_MODEL = "chronbmm/sanskrit5-multitask"


def _masked_mean_pool(
    hidden_states: torch.Tensor, attention_mask: torch.Tensor
) -> torch.Tensor:
    """Attention-masked mean pool over the sequence axis.

    hidden_states: (B, T, D)
    attention_mask: (B, T), 1 for real tokens, 0 for pads.
    Returns: (B, D)
    """
    mask = attention_mask.unsqueeze(-1).float()
    summed = (hidden_states * mask).sum(dim=1)
    counts = mask.sum(dim=1).clamp(min=1e-9)
    return summed / counts


def _auto_device() -> str:
    """Pick the best available torch backend."""
    if torch.backends.mps.is_available():
        return "mps"
    if torch.cuda.is_available():
        return "cuda"
    return "cpu"


class ByT5SanskritEmbedder:
    """Encoder-only pooled embedder for ByT5 Sanskrit models.

    Uses the encoder `last_hidden_state` with attention-masked mean pooling.
    Output dimension is the model's native `d_model` (1472 for byt5-small,
    1536 for byt5-base). Projection to a fixed target dimension is the
    ProjectionHead's responsibility, not this class.
    """

    def __init__(
        self,
        model_name: str = _DEFAULT_MODEL,
        device: Optional[str] = None,
        max_length: int = 1024,
        normalize: bool = True,
        lazy: bool = False,
    ) -> None:
        self.model_name = model_name
        self.device = device or _auto_device()
        self.max_length = max_length
        self.normalize = normalize
        self._model: Optional[T5ForConditionalGeneration] = None
        self._tokenizer: Optional[ByT5Tokenizer] = None
        if not lazy:
            self._load()

    @property
    def embedding_dim(self) -> int:
        if self._model is None:
            self._load()
        return int(self._model.config.d_model)

    def _load(self) -> None:
        if self._model is not None:
            return
        logger.info("Loading ByT5 model %s on %s", self.model_name, self.device)
        self._tokenizer = ByT5Tokenizer.from_pretrained(self.model_name)
        model = T5ForConditionalGeneration.from_pretrained(self.model_name)
        # Disable dropout/batchnorm at inference time
        model.train(False)
        model.to(self.device)
        self._model = model
