"""ByT5-based Sanskrit embeddings.

Provides encoder-only pooled embeddings from the Dharmamitra ByT5 model,
complementary to purpose-built sentence encoders like Vyakyarth.
"""

from sanskrit_analyzer.embeddings.byt5_embedder import ByT5SanskritEmbedder

__all__ = ["ByT5SanskritEmbedder"]
