"""Sentence embedding backends for Sanskrit and multilingual text.

Provides:
* :class:`ByT5SanskritEmbedder` — ByT5 encoder with masked mean pooling for Sanskrit.
* :class:`BgeM3Embedder` — BAAI/bge-m3 dense vectors via sentence-transformers for English.
* :class:`Embedder` — Protocol that both classes satisfy structurally.
"""

from sanskrit_analyzer.embeddings.base import Embedder
from sanskrit_analyzer.embeddings.bge_m3_embedder import BgeM3Embedder
from sanskrit_analyzer.embeddings.byt5_embedder import ByT5SanskritEmbedder

__all__ = ["Embedder", "BgeM3Embedder", "ByT5SanskritEmbedder"]
