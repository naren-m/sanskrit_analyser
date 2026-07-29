"""
Sanskrit Analyzer - Centralized Sanskrit sentence parser with ensemble analysis.

This package provides:
- 4-level parse trees (Sentence -> Sandhi Groups -> Base Words -> Dhatus)
- ensemble (Vidyut, Sanskrit Heritage, local ByT5)
- Hybrid disambiguation (Rules -> LLM -> Human)
- Tiered caching (Memory -> Redis -> SQLite)
"""

__version__ = "0.1.0"
__author__ = "Naren Mudivarthy"

from sanskrit_analyzer.analyzer import Analyzer
from sanskrit_analyzer.config import AnalysisMode, Config, ConfigError
from sanskrit_analyzer.deep_read import DeepRead, DeepReadResult

__all__ = [
    "__version__",
    "Analyzer",
    "AnalysisMode",
    "Config",
    "ConfigError",
    "DeepRead",
    "DeepReadResult",
]
