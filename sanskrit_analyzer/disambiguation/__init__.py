"""Disambiguation pipeline for ambiguous parses."""

from sanskrit_analyzer.disambiguation.llm import (
    LLMConfig,
    LLMDisambiguationResult,
    LLMDisambiguator,
    LLMProvider,
)
from sanskrit_analyzer.disambiguation.rules import (
    DisambiguationRule,
    FrequencyPreferenceRule,
    GenderNumberAgreementRule,
    ParseCandidate,
    RuleBasedDisambiguator,
    RuleBasedDisambiguatorConfig,
    RuleConfig,
    RuleResult,
    RuleType,
    SandhiPreferenceRule,
)

__all__ = [
    "DisambiguationRule",
    "FrequencyPreferenceRule",
    "GenderNumberAgreementRule",
    "LLMConfig",
    "LLMDisambiguationResult",
    "LLMDisambiguator",
    "LLMProvider",
    "ParseCandidate",
    "RuleBasedDisambiguator",
    "RuleBasedDisambiguatorConfig",
    "RuleConfig",
    "RuleResult",
    "RuleType",
    "SandhiPreferenceRule",
]
