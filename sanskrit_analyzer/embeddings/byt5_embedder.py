"""ByT5-based Sanskrit embedder using encoder mean pooling.

See docs/superpowers/specs/2026-04-18-byt5-sanskrit-embeddings-design.md
in the ramayanam repo for the design rationale.
"""

from __future__ import annotations

import logging
from typing import Optional

import numpy as np
import torch
import torch.nn.functional as F
from transformers import ByT5Tokenizer, T5ForConditionalGeneration

logger = logging.getLogger(__name__)

_DEFAULT_MODEL = "chronbmm/sanskrit5-multitask"

# Pinned so an upstream re-upload cannot silently change the produced vectors.
# TODO: replace this tag with a specific commit SHA once one is confirmed.
_DEFAULT_REVISION = "main"

# Native ``d_model`` of the default model (ByT5-small backbone). Used only for
# the empty-input fast path so it can return a correctly-shaped ``(0, d)``
# array without forcing a full model load.
_DEFAULT_D_MODEL = 1472


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
        revision: str = _DEFAULT_REVISION,
    ) -> None:
        self.model_name = model_name
        self.device = device or _auto_device()
        self.max_length = max_length
        self.normalize = normalize
        self.revision = revision
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
        self._tokenizer = ByT5Tokenizer.from_pretrained(
            self.model_name, revision=self.revision
        )
        model = T5ForConditionalGeneration.from_pretrained(
            self.model_name, revision=self.revision
        )
        # Disable dropout/batchnorm at inference time
        model.train(False)
        model.to(self.device)
        self._model = model

    def encode(self, texts: list[str], batch_size: int = 8) -> np.ndarray:
        """Devanagari or IAST → (N, d_model) embeddings, optionally L2-normalized."""
        if len(texts) == 0:
            # Short-circuit before touching ``embedding_dim`` so an empty batch
            # never forces a full model load. Use the loaded model's dim if
            # available, else the known default-model constant.
            dim = (
                int(self._model.config.d_model)
                if self._model is not None
                else _DEFAULT_D_MODEL
            )
            return np.zeros((0, dim), dtype=np.float32)
        if self._model is None:
            self._load()

        all_pooled: list[torch.Tensor] = []
        with torch.no_grad():
            for start in range(0, len(texts), batch_size):
                batch = texts[start : start + batch_size]
                enc = self._tokenizer(
                    batch,
                    padding=True,
                    truncation=True,
                    max_length=self.max_length,
                    return_tensors="pt",
                )
                input_ids = enc["input_ids"].to(self.device)
                attention_mask = enc["attention_mask"].to(self.device)

                encoder_out = self._model.encoder(
                    input_ids=input_ids,
                    attention_mask=attention_mask,
                    return_dict=True,
                )
                pooled = _masked_mean_pool(
                    encoder_out.last_hidden_state, attention_mask
                )
                if self.normalize:
                    pooled = F.normalize(pooled, p=2, dim=1)
                all_pooled.append(pooled.cpu())

        return torch.cat(all_pooled, dim=0).numpy().astype(np.float32)
