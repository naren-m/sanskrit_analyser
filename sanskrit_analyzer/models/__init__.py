"""Data models for Sanskrit analysis."""

from sanskrit_analyzer.models.dhatu import COMMON_DHATUS, DhatuInfo, Gana, Pada
from sanskrit_analyzer.models.morphology import (
    Case,
    Gender,
    Meaning,
    MorphologicalTag,
    Number,
    PartOfSpeech,
    Person,
    Pratyaya,
    SandhiType,
    Tense,
    Voice,
)
from sanskrit_analyzer.models.scripts import Script, ScriptVariants

__all__ = [
    # Scripts
    "Script",
    "ScriptVariants",
    # Morphology
    "PartOfSpeech",
    "Gender",
    "Number",
    "Case",
    "Person",
    "Tense",
    "Voice",
    "SandhiType",
    "MorphologicalTag",
    "Pratyaya",
    "Meaning",
    # Dhatu
    "DhatuInfo",
    "Gana",
    "Pada",
    "COMMON_DHATUS",
]
