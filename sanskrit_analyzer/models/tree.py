"""Parse tree data models for Sanskrit analysis.

This module defines the 4-level hierarchical structure:
  Sentence (AnalysisTree)
    └── Sandhi Groups (SandhiGroup)
          └── Base Words (BaseWord)
                └── Dhatus (DhatuInfo)
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

from sanskrit_analyzer.models.dhatu import DhatuInfo
from sanskrit_analyzer.models.morphology import (
    Meaning,
    MorphologicalTag,
    Pratyaya,
    SandhiType,
)
from sanskrit_analyzer.models.scripts import ScriptVariants


class CacheTier(Enum):
    """Cache tier where an analysis was found."""

    MEMORY = "memory"
    REDIS = "redis"
    SQLITE = "sqlite"
    NONE = "none"  # Not cached, freshly computed


class CompoundType(Enum):
    """Types of Sanskrit compounds (samāsa)."""

    TATPURUSHA = "tatpuruṣa"  # Determinative compound
    DVANDVA = "dvandva"  # Copulative compound
    BAHUVRIHI = "bahuvrīhi"  # Possessive compound
    AVYAYIBHAVA = "avyayībhāva"  # Adverbial compound
    KARMADHARAYA = "karmadhāraya"  # Appositional (subtype of tatpurusha)
    DVIGU = "dvigu"  # Numeral (subtype of tatpurusha)
    UNKNOWN = "unknown"


@dataclass
class ConfidenceMetrics:
    """Confidence metrics for an analysis result."""

    overall: float  # Overall confidence (0.0-1.0)
    engine_agreement: float  # How much engines agreed (0.0-1.0)
    disambiguation_applied: bool = False  # Whether disambiguation was needed
    disambiguation_stage: Optional[str] = None  # "rules", "llm", or "human"

    def __post_init__(self) -> None:
        """Validate confidence values."""
        self.overall = max(0.0, min(1.0, self.overall))
        self.engine_agreement = max(0.0, min(1.0, self.engine_agreement))


@dataclass
class BaseWord:
    """Individual word after sandhi splitting (Level 3).

    Represents a single morphological unit with its analysis.
    """

    lemma: str  # Dictionary form (in SLP1)
    surface_form: str  # Form as it appears in context
    scripts: ScriptVariants  # All script representations
    morphology: Optional[MorphologicalTag] = None  # Grammatical analysis
    meanings: list[Meaning] = field(default_factory=list)  # Dictionary meanings
    dhatu: Optional[DhatuInfo] = None  # Verbal root (if verb-derived)
    pratyaya: list[Pratyaya] = field(default_factory=list)  # Suffixes applied
    upasarga: list[str] = field(default_factory=list)  # Prefixes (preverbs)
    confidence: float = 1.0  # Analysis confidence

    @property
    def primary_meaning(self) -> Optional[str]:
        """Get the primary meaning."""
        return str(self.meanings[0]) if self.meanings else None

    @property
    def is_verb_derived(self) -> bool:
        """Check if this word is derived from a verbal root."""
        return self.dhatu is not None

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "lemma": self.lemma,
            "surface_form": self.surface_form,
            "devanagari": self.scripts.devanagari,
            "iast": self.scripts.iast,
            "morphology": self.morphology.to_string() if self.morphology else None,
            "meanings": [str(m) for m in self.meanings],
            "dhatu": str(self.dhatu) if self.dhatu else None,
            "upasarga": self.upasarga,
            "confidence": self.confidence,
        }


@dataclass
class SandhiGroup:
    """A sandhi-joined unit (Level 2).

    Represents a continuous sequence of characters that may contain
    one or more words joined by sandhi rules.
    """

    surface_form: str  # As it appears in the text
    scripts: ScriptVariants  # All script representations
    sandhi_type: Optional[SandhiType] = None  # Type of sandhi applied
    sandhi_rule: Optional[str] = None  # Ashtadhyayi sutra reference
    is_compound: bool = False  # Whether this is a compound word
    compound_type: Optional[CompoundType] = None  # Type of compound
    base_words: list[BaseWord] = field(default_factory=list)  # Component words

    @property
    def word_count(self) -> int:
        """Number of base words in this group."""
        return len(self.base_words)

    @property
    def is_single_word(self) -> bool:
        """Check if this group contains a single word (no sandhi split)."""
        return len(self.base_words) == 1

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "surface_form": self.surface_form,
            "devanagari": self.scripts.devanagari,
            "iast": self.scripts.iast,
            "sandhi_type": self.sandhi_type.value if self.sandhi_type else None,
            "sandhi_rule": self.sandhi_rule,
            "is_compound": self.is_compound,
            "compound_type": self.compound_type.value if self.compound_type else None,
            "base_words": [w.to_dict() for w in self.base_words],
        }


@dataclass
class ParseTree:
    """One complete parse interpretation of the sentence.

    Multiple ParseTree instances may exist for an ambiguous sentence,
    representing different valid interpretations.
    """

    parse_id: str  # Unique identifier for this parse
    confidence: float  # Overall confidence (0.0-1.0)
    engine_votes: dict[str, float] = field(default_factory=dict)  # Per-engine scores
    sandhi_groups: list[SandhiGroup] = field(default_factory=list)  # Level 2 nodes

    @property
    def word_count(self) -> int:
        """Total number of base words across all sandhi groups."""
        return sum(sg.word_count for sg in self.sandhi_groups)

    @property
    def all_words(self) -> list[BaseWord]:
        """Flatten all base words from all sandhi groups."""
        words = []
        for sg in self.sandhi_groups:
            words.extend(sg.base_words)
        return words

    @property
    def all_dhatus(self) -> list[DhatuInfo]:
        """Get all dhatus found in this parse."""
        return [w.dhatu for w in self.all_words if w.dhatu is not None]

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "parse_id": self.parse_id,
            "confidence": self.confidence,
            "engine_votes": self.engine_votes,
            "word_count": self.word_count,
            "sandhi_groups": [sg.to_dict() for sg in self.sandhi_groups],
        }


@dataclass
class AnalysisTree:
    """Root container for a complete sentence analysis (Level 1).

    This is the top-level structure containing all parse interpretations
    and metadata about the analysis.
    """

    sentence_id: str  # Unique identifier
    original_text: str  # Raw input text
    normalized_slp1: str  # Normalized to SLP1
    scripts: ScriptVariants  # All script representations
    parse_forest: list[ParseTree] = field(default_factory=list)  # All valid parses
    selected_parse: Optional[int] = None  # Index of user-selected parse
    confidence: ConfidenceMetrics = field(
        default_factory=lambda: ConfidenceMetrics(overall=0.0, engine_agreement=0.0)
    )
    mode: str = "production"  # Analysis mode used
    cached_at: CacheTier = CacheTier.NONE  # Where this was cached

    @property
    def best_parse(self) -> Optional[ParseTree]:
        """Get the best (or selected) parse interpretation."""
        if not self.parse_forest:
            return None
        if self.selected_parse is not None and 0 <= self.selected_parse < len(
            self.parse_forest
        ):
            return self.parse_forest[self.selected_parse]
        # Return highest confidence parse
        return max(self.parse_forest, key=lambda p: p.confidence)

    @property
    def parse_count(self) -> int:
        """Number of valid parse interpretations."""
        return len(self.parse_forest)

    @property
    def is_ambiguous(self) -> bool:
        """Check if there are multiple valid parses."""
        return len(self.parse_forest) > 1

    @property
    def all_words(self) -> list[BaseWord]:
        """Get all words from the best parse."""
        best = self.best_parse
        return best.all_words if best else []

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "sentence_id": self.sentence_id,
            "original_text": self.original_text,
            "normalized_slp1": self.normalized_slp1,
            "scripts": {
                "devanagari": self.scripts.devanagari,
                "iast": self.scripts.iast,
                "slp1": self.scripts.slp1,
            },
            "parse_forest": [p.to_dict() for p in self.parse_forest],
            "parse_count": self.parse_count,
            "is_ambiguous": self.is_ambiguous,
            "selected_parse": self.selected_parse,
            "confidence": {
                "overall": self.confidence.overall,
                "engine_agreement": self.confidence.engine_agreement,
                "disambiguation_applied": self.confidence.disambiguation_applied,
            },
            "mode": self.mode,
            "cached_at": self.cached_at.value,
        }

    def select_parse(self, index: int) -> None:
        """Select a specific parse as the correct interpretation.

        Args:
            index: Index of the parse to select.

        Raises:
            IndexError: If index is out of range.
        """
        if not 0 <= index < len(self.parse_forest):
            raise IndexError(f"Parse index {index} out of range [0, {len(self.parse_forest)})")
        self.selected_parse = index
        self.confidence.disambiguation_applied = True
        self.confidence.disambiguation_stage = "human"
