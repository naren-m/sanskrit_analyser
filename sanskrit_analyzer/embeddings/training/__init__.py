"""Projection-head training over frozen Sanskrit embedders.

Phase A.2 of the ByT5 Sanskrit embeddings work. See
docs/superpowers/specs/2026-04-18-byt5-sanskrit-embeddings-design.md
in the ramayanam repo for the design rationale.
"""

from sanskrit_analyzer.embeddings.training.adapted_embedder import (
    AdaptedEmbedder,
)
from sanskrit_analyzer.embeddings.training.history import TrainingHistory
from sanskrit_analyzer.embeddings.training.info_nce import info_nce_loss
from sanskrit_analyzer.embeddings.training.projection_head import (
    ProjectionHead,
)
from sanskrit_analyzer.embeddings.training.trainer import (
    ProjectionHeadTrainer,
)

__all__ = [
    "AdaptedEmbedder",
    "ProjectionHead",
    "ProjectionHeadTrainer",
    "TrainingHistory",
    "info_nce_loss",
]
