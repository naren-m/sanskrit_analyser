"""ByT5-based Sanskrit embedder using encoder mean pooling.

See docs/superpowers/specs/2026-04-18-byt5-sanskrit-embeddings-design.md
in the ramayanam repo for the design rationale.
"""

from __future__ import annotations

import torch


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


class ByT5SanskritEmbedder:
    """Placeholder — full implementation lands in Task 3 of the Phase A.1 plan."""
