"""Projection-head training over frozen Sanskrit embedders.

Phase A.2 of the ByT5 Sanskrit embeddings work. See
docs/superpowers/specs/2026-04-18-byt5-sanskrit-embeddings-design.md
in the ramayanam repo for the design rationale.

Public exports are populated incrementally as each submodule lands.
Import directly from submodule paths (e.g.
sanskrit_analyzer.embeddings.training.projection_head) until the final
trainer module ships, which restores the convenience re-exports below.
"""

__all__: list[str] = []
