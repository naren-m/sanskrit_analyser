"""Prakriyā engine: verse-to-dhātu analysis with Pāṇinian rule tracing.

Phase 1+2 of docs/prakriya-engine-design.md: normalization, chandas
identification, and single-pada analysis-by-synthesis over vidyut.
"""
from sanskrit_analyzer.prakriya.engine import analyze_verse

__all__ = ["analyze_verse"]
