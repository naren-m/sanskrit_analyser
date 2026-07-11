"""Trainable projection head over a frozen Sanskrit encoder."""

from __future__ import annotations

import json
from pathlib import Path

import torch
import torch.nn as nn
import torch.nn.functional as F


class ProjectionHead(nn.Module):
    """2-layer MLP projecting encoder output to a target dimension.

    Architecture: input_dim -> hidden_dim (GELU) -> output_dim, optionally
    L2-normalized. Tiny enough (~3MB at fp32 for 1536->1024->768) to ship
    as a separate adapter artifact alongside the frozen encoder.
    """

    def __init__(
        self,
        input_dim: int,
        hidden_dim: int = 1024,
        output_dim: int = 768,
        normalize: bool = True,
    ) -> None:
        super().__init__()
        self.input_dim = input_dim
        self.hidden_dim = hidden_dim
        self.output_dim = output_dim
        self.normalize = normalize
        self.fc1 = nn.Linear(input_dim, hidden_dim)
        self.fc2 = nn.Linear(hidden_dim, output_dim)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        h = F.gelu(self.fc1(x))
        out = self.fc2(h)
        if self.normalize:
            out = F.normalize(out, p=2, dim=-1)
        return out

    def save(self, path: Path) -> None:
        """Save weights to ``path`` and config to a ``.config.json`` sidecar.

        The config is stored as JSON (not pickled alongside the tensors) so the
        checkpoint can be reloaded with ``weights_only=True``, which forbids
        arbitrary-code execution during unpickling.
        """
        path = Path(path)
        torch.save({"state_dict": self.state_dict()}, path)
        self._config_path(path).write_text(
            json.dumps(
                {
                    "input_dim": self.input_dim,
                    "hidden_dim": self.hidden_dim,
                    "output_dim": self.output_dim,
                    "normalize": self.normalize,
                }
            )
        )

    @classmethod
    def load(cls, path: Path) -> "ProjectionHead":
        path = Path(path)
        config = json.loads(cls._config_path(path).read_text())
        payload = torch.load(path, map_location="cpu", weights_only=True)
        head = cls(**config)
        head.load_state_dict(payload["state_dict"])
        head.train(False)
        return head

    @staticmethod
    def _config_path(path: Path) -> Path:
        """Sidecar JSON path for a checkpoint (``foo.pt`` -> ``foo.config.json``)."""
        return path.with_suffix(path.suffix + ".config.json")
