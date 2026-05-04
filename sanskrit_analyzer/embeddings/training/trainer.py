"""Train a projection head over a frozen Sanskrit embedder."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Optional

import numpy as np
import torch

from sanskrit_analyzer.embeddings.training.history import TrainingHistory
from sanskrit_analyzer.embeddings.training.info_nce import info_nce_loss
from sanskrit_analyzer.embeddings.training.projection_head import (
    ProjectionHead,
)

logger = logging.getLogger(__name__)


class ProjectionHeadTrainer:
    """Fits a ProjectionHead on top of a frozen embedder using InfoNCE.

    Encoder parameters are never passed to the optimizer; only the head
    receives gradients. Verified by tests/embeddings/training/test_trainer.py.
    """

    def __init__(
        self,
        embedder,
        output_dim: int = 768,
        hidden_dim: int = 1024,
        temperature: float = 0.05,
        learning_rate: float = 1e-4,
        device: Optional[str] = None,
    ) -> None:
        self.embedder = embedder
        self.temperature = temperature
        self.device = device or "cpu"
        self.head = ProjectionHead(
            input_dim=embedder.embedding_dim,
            hidden_dim=hidden_dim,
            output_dim=output_dim,
        ).to(self.device)
        self._optimizer = torch.optim.AdamW(
            self.head.parameters(), lr=learning_rate
        )
        self.history = TrainingHistory()

    def _encode_texts(self, texts: list[str]) -> torch.Tensor:
        raw = self.embedder.encode(texts)
        return torch.from_numpy(raw).to(self.device)

    def _epoch_loss(
        self,
        pairs: list[tuple[str, str, int]],
        batch_size: int,
        train: bool,
    ) -> float:
        if train:
            self.head.train()
        else:
            self.head.train(False)
        total = 0.0
        n_batches = 0
        order = (
            np.random.permutation(len(pairs))
            if train
            else np.arange(len(pairs))
        )
        for start in range(0, len(pairs), batch_size):
            idx = order[start : start + batch_size]
            batch = [pairs[i] for i in idx]
            a_texts = [p[0] for p in batch]
            b_texts = [p[1] for p in batch]
            labels = torch.tensor(
                [int(p[2]) for p in batch], dtype=torch.int64, device=self.device
            )

            raw_a = self._encode_texts(a_texts)
            raw_b = self._encode_texts(b_texts)

            grad_ctx = torch.enable_grad() if train else torch.no_grad()
            with grad_ctx:
                proj_a = self.head(raw_a)
                proj_b = self.head(raw_b)
                loss = info_nce_loss(
                    proj_a, proj_b, labels, temperature=self.temperature
                )

            if train and loss.requires_grad and loss.item() != 0.0:
                self._optimizer.zero_grad()
                loss.backward()
                self._optimizer.step()

            total += float(loss.item())
            n_batches += 1
        return total / max(n_batches, 1)

    def fit(
        self,
        pairs: list[tuple[str, str, int]],
        epochs: int = 10,
        batch_size: int = 16,
        val_pairs: Optional[list[tuple[str, str, int]]] = None,
    ) -> TrainingHistory:
        for epoch in range(epochs):
            train_loss = self._epoch_loss(pairs, batch_size, train=True)
            val_loss = (
                self._epoch_loss(val_pairs, batch_size, train=False)
                if val_pairs
                else None
            )
            self.history.record(epoch, train_loss, val_loss)
            logger.info(
                "epoch=%d train_loss=%.4f val_loss=%s",
                epoch,
                train_loss,
                f"{val_loss:.4f}" if val_loss is not None else "n/a",
            )
        return self.history

    def save(self, path: Path) -> None:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        self.head.save(path)
        history_path = path.with_suffix(".history.json")
        history_path.write_text(json.dumps(self.history.to_dict(), indent=2))
