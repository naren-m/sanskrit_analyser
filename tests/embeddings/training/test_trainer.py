"""Tests for ProjectionHeadTrainer."""

from pathlib import Path

import numpy as np
import pytest
import torch

from sanskrit_analyzer.embeddings.training.adapted_embedder import (
    AdaptedEmbedder,
)
from sanskrit_analyzer.embeddings.training.projection_head import (
    ProjectionHead,
)
from sanskrit_analyzer.embeddings.training.trainer import (
    ProjectionHeadTrainer,
)


class _StubEmbedder:
    """Stand-in for ByT5SanskritEmbedder with reproducible outputs."""

    def __init__(self, dim: int = 16):
        self._dim = dim
        self._w = torch.nn.Parameter(torch.randn(dim, dim))

    @property
    def embedding_dim(self) -> int:
        return self._dim

    def encode(self, texts: list[str], batch_size: int = 8) -> np.ndarray:
        if not texts:
            return np.zeros((0, self._dim), dtype=np.float32)
        rng = np.random.default_rng(
            seed=abs(hash(tuple(texts))) % (2**32 - 1)
        )
        return rng.standard_normal((len(texts), self._dim)).astype(np.float32)


def _make_pairs(n: int) -> list[tuple[str, str, int]]:
    return [(f"a-{i}", f"b-{i}", 1) for i in range(n)]


class TestTrainerConstruction:
    def test_optimizer_only_holds_head_params(self):
        embedder = _StubEmbedder(dim=16)
        trainer = ProjectionHeadTrainer(
            embedder=embedder, output_dim=8, hidden_dim=12
        )
        opt_params = {id(p) for g in trainer._optimizer.param_groups for p in g["params"]}
        head_params = {id(p) for p in trainer.head.parameters()}
        assert opt_params == head_params

    def test_head_input_dim_matches_embedder(self):
        embedder = _StubEmbedder(dim=16)
        trainer = ProjectionHeadTrainer(embedder=embedder, output_dim=4)
        assert trainer.head.input_dim == 16
        assert trainer.head.output_dim == 4


class TestTrainerFit:
    def test_fit_returns_history_with_one_loss_per_epoch(self):
        embedder = _StubEmbedder(dim=16)
        trainer = ProjectionHeadTrainer(
            embedder=embedder, output_dim=8, hidden_dim=12
        )
        history = trainer.fit(_make_pairs(8), epochs=3, batch_size=4)
        assert len(history.epochs) == 3
        assert len(history.train_loss) == 3
        for loss in history.train_loss:
            assert loss == loss  # not NaN

    def test_fit_decreases_loss_on_easy_synthetic_task(self):
        torch.manual_seed(0)
        np.random.seed(0)
        embedder = _StubEmbedder(dim=16)
        trainer = ProjectionHeadTrainer(
            embedder=embedder,
            output_dim=8,
            hidden_dim=12,
            learning_rate=1e-2,
        )
        pairs = _make_pairs(16)
        h = trainer.fit(pairs, epochs=5, batch_size=8)
        assert h.train_loss[-1] < h.train_loss[0]

    def test_val_loss_recorded_when_val_pairs_provided(self):
        embedder = _StubEmbedder(dim=16)
        trainer = ProjectionHeadTrainer(
            embedder=embedder, output_dim=8, hidden_dim=12
        )
        train = _make_pairs(8)
        val = _make_pairs(4)
        h = trainer.fit(train, epochs=2, batch_size=4, val_pairs=val)
        assert all(v is not None for v in h.val_loss)


class TestTrainerSaveLoad:
    def test_save_writes_checkpoint_and_history(self, tmp_path: Path):
        embedder = _StubEmbedder(dim=16)
        trainer = ProjectionHeadTrainer(
            embedder=embedder, output_dim=8, hidden_dim=12
        )
        trainer.fit(_make_pairs(8), epochs=2, batch_size=4)
        ckpt = tmp_path / "adapter.pt"
        trainer.save(ckpt)
        assert ckpt.exists()
        assert ckpt.with_suffix(".history.json").exists()

    def test_load_restores_head_outputs(self, tmp_path: Path):
        embedder = _StubEmbedder(dim=16)
        trainer = ProjectionHeadTrainer(
            embedder=embedder, output_dim=8, hidden_dim=12
        )
        trainer.fit(_make_pairs(8), epochs=2, batch_size=4)
        ckpt = tmp_path / "adapter.pt"
        trainer.save(ckpt)

        loaded_head = ProjectionHead.load(ckpt)
        adapted = AdaptedEmbedder(embedder, loaded_head)
        out = adapted.encode(["x", "y"])
        assert out.shape == (2, 8)
