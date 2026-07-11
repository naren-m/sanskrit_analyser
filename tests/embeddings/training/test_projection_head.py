"""Tests for ProjectionHead."""

import json
from pathlib import Path

import pytest
import torch

from sanskrit_analyzer.embeddings.training.projection_head import (
    ProjectionHead,
)


class TestProjectionHeadForward:
    def test_forward_returns_expected_shape(self):
        head = ProjectionHead(input_dim=1536, hidden_dim=1024, output_dim=768)
        x = torch.randn(4, 1536)
        out = head(x)
        assert out.shape == (4, 768)

    def test_default_dims_match_spec(self):
        head = ProjectionHead(input_dim=1536)
        assert head.input_dim == 1536
        assert head.hidden_dim == 1024
        assert head.output_dim == 768

    def test_output_is_l2_normalized_when_normalize_true(self):
        head = ProjectionHead(input_dim=8, hidden_dim=16, output_dim=4, normalize=True)
        x = torch.randn(5, 8)
        out = head(x)
        norms = out.norm(dim=1)
        torch.testing.assert_close(
            norms, torch.ones(5), rtol=1e-5, atol=1e-5
        )

    def test_no_nan_on_zero_input(self):
        head = ProjectionHead(input_dim=8, hidden_dim=16, output_dim=4)
        out = head(torch.zeros(2, 8))
        assert torch.isfinite(out).all()


class TestProjectionHeadSaveLoad:
    def test_round_trip_preserves_outputs(self, tmp_path: Path):
        head = ProjectionHead(input_dim=8, hidden_dim=16, output_dim=4)
        x = torch.randn(3, 8)
        before = head(x).detach().clone()

        ckpt = tmp_path / "head.pt"
        head.save(ckpt)

        loaded = ProjectionHead.load(ckpt)
        after = loaded(x).detach()
        torch.testing.assert_close(before, after, rtol=1e-6, atol=1e-6)

    def test_load_restores_dims(self, tmp_path: Path):
        head = ProjectionHead(input_dim=11, hidden_dim=22, output_dim=7)
        ckpt = tmp_path / "head.pt"
        head.save(ckpt)

        loaded = ProjectionHead.load(ckpt)
        assert loaded.input_dim == 11
        assert loaded.hidden_dim == 22
        assert loaded.output_dim == 7

    def test_config_written_as_json_sidecar(self, tmp_path: Path):
        head = ProjectionHead(input_dim=8, hidden_dim=16, output_dim=4)
        ckpt = tmp_path / "head.pt"
        head.save(ckpt)

        sidecar = tmp_path / "head.pt.config.json"
        assert sidecar.exists()
        config = json.loads(sidecar.read_text())
        assert config == {
            "input_dim": 8,
            "hidden_dim": 16,
            "output_dim": 4,
            "normalize": True,
        }

    def test_checkpoint_loads_with_weights_only(self, tmp_path: Path):
        """Weights load under ``weights_only=True`` (no pickled config)."""
        head = ProjectionHead(input_dim=8, hidden_dim=16, output_dim=4)
        ckpt = tmp_path / "head.pt"
        head.save(ckpt)

        payload = torch.load(ckpt, map_location="cpu", weights_only=True)
        assert "state_dict" in payload
