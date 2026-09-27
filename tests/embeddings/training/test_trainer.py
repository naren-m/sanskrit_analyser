"""Tests for ProjectionHeadTrainer."""

from pathlib import Path

import numpy as np
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
        rng = np.random.default_rng(seed=abs(hash(tuple(texts))) % (2**32 - 1))
        return rng.standard_normal((len(texts), self._dim)).astype(np.float32)


def _make_pairs(n: int) -> list[tuple[str, str, int]]:
    return [(f"a-{i}", f"b-{i}", 1) for i in range(n)]


def _trainer(embedder: _StubEmbedder | None = None, **kwargs) -> ProjectionHeadTrainer:
    return ProjectionHeadTrainer(
        embedder=embedder or _StubEmbedder(dim=16), output_dim=8, hidden_dim=12, **kwargs
    )


def test_construction():
    trainer = _trainer()
    # Only the head trains; the embedder stays frozen.
    opt_params = {id(p) for g in trainer._optimizer.param_groups for p in g["params"]}
    assert opt_params == {id(p) for p in trainer.head.parameters()}
    # The head's input is sized from the embedder.
    assert trainer.head.input_dim == 16
    assert trainer.head.output_dim == 8


def test_fit():
    h = _trainer().fit(_make_pairs(8), epochs=3, batch_size=4)
    assert len(h.epochs) == 3
    assert len(h.train_loss) == 3
    for loss in h.train_loss:
        assert loss == loss  # not NaN

    h = _trainer().fit(_make_pairs(8), epochs=2, batch_size=4, val_pairs=_make_pairs(4))
    assert all(v is not None for v in h.val_loss)

    torch.manual_seed(0)
    np.random.seed(0)
    h = _trainer(learning_rate=1e-2).fit(_make_pairs(16), epochs=5, batch_size=8)
    assert h.train_loss[-1] < h.train_loss[0], "loss should drop on an easy synthetic task"


def test_save_load(tmp_path: Path):
    embedder = _StubEmbedder(dim=16)
    trainer = _trainer(embedder)
    trainer.fit(_make_pairs(8), epochs=2, batch_size=4)
    ckpt = tmp_path / "adapter.pt"
    trainer.save(ckpt)
    assert ckpt.exists()
    assert ckpt.with_suffix(".history.json").exists()

    adapted = AdaptedEmbedder(embedder, ProjectionHead.load(ckpt))
    assert adapted.encode(["x", "y"]).shape == (2, 8)
