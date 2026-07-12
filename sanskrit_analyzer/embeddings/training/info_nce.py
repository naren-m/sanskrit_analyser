"""InfoNCE contrastive loss for projected embedding pairs."""

from __future__ import annotations

import torch
import torch.nn.functional as F


def info_nce_loss(
    a: torch.Tensor,
    b: torch.Tensor,
    labels: torch.Tensor,
    temperature: float = 0.05,
) -> torch.Tensor:
    """Symmetric InfoNCE over label=1 pairs with in-batch negatives.

    a, b: (B, D) - paired embeddings, same row index = paired sample.
    labels: (B,) - 1 = positive pair, 0 = negative pair (currently
      excluded from the positive-term computation; in-batch negatives
      provide the contrast).
    temperature: softmax temperature; lower = sharper, harder negatives.

    Returns a 0-dim loss tensor. If fewer than 2 positives exist,
    returns 0.0 (no in-batch negatives possible).
    """
    pos_mask = labels == 1
    a_pos = a[pos_mask]
    b_pos = b[pos_mask]
    n_pos = a_pos.shape[0]
    if n_pos < 2:
        return torch.tensor(0.0, device=a.device, requires_grad=True)

    sims_ab = (a_pos @ b_pos.T) / temperature
    targets = torch.arange(n_pos, device=a.device)
    loss_ab = F.cross_entropy(sims_ab, targets)

    sims_ba = (b_pos @ a_pos.T) / temperature
    loss_ba = F.cross_entropy(sims_ba, targets)
    return 0.5 * (loss_ab + loss_ba)
