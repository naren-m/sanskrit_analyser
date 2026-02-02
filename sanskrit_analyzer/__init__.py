"""
Sanskrit Analyzer - Centralized Sanskrit sentence parser with 3-engine ensemble analysis.

This package provides:
- 4-level parse trees (Sentence -> Sandhi Groups -> Base Words -> Dhatus)
- 3-engine ensemble (Vidyut, Dharmamitra ByT5, Sanskrit Heritage)
- Hybrid disambiguation (Rules -> LLM -> Human)
- Tiered caching (Memory -> Redis -> SQLite)
"""

__version__ = "0.1.0"
__author__ = "Naren Mudivarthy"

from sanskrit_analyzer.analyzer import Analyzer
from sanskrit_analyzer.config import AnalysisMode, Config

__all__ = [
    "__version__",
    "Analyzer",
    "AnalysisMode",
    "Config",
]
