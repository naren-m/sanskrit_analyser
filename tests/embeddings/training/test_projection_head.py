"""Tests for ProjectionHead."""

from pathlib import Path

import torch

from sanskrit_analyzer.embeddings.training.projection_head import (
    ProjectionHead,
)


def test_forward():
    # Spec dims: 1536 -> 1024 -> 768 by default.
    head = ProjectionHead(input_dim=1536)
    assert (head.hidden_dim, head.output_dim) == (1024, 768)
    assert head(torch.randn(4, 1536)).shape == (4, 768)

    small = ProjectionHead(input_dim=8, hidden_dim=16, output_dim=4, normalize=True)
    norms = small(torch.randn(5, 8)).norm(dim=1)
    torch.testing.assert_close(norms, torch.ones(5), rtol=1e-5, atol=1e-5)

    plain = ProjectionHead(input_dim=8, hidden_dim=16, output_dim=4)
    assert torch.isfinite(plain(torch.zeros(2, 8))).all()


def test_save_load_round_trip(tmp_path: Path):
    head = ProjectionHead(input_dim=11, hidden_dim=22, output_dim=7)
    x = torch.randn(3, 11)
    before = head(x).detach().clone()

    ckpt = tmp_path / "head.pt"
    head.save(ckpt)
    loaded = ProjectionHead.load(ckpt)

    assert (loaded.input_dim, loaded.hidden_dim, loaded.output_dim) == (11, 22, 7)
    torch.testing.assert_close(before, loaded(x).detach(), rtol=1e-6, atol=1e-6)
