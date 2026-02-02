"""Abstract base class for analysis engines."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class SandhiInfo:
    """Information about sandhi applied at a segment boundary."""

    type: str  # Type of sandhi (e.g., "vowel", "visarga", "consonant")
    rule: Optional[str] = None  # Ashtadhyayi sutra if known
    original_ending: Optional[str] = None  # What was before sandhi
    original_beginning: Optional[str] = None  # What followed before sandhi


@dataclass
class Segment:
    """A single analyzed segment from an engine.

    This is the common format that all engines produce.
    """

    surface: str  # The form as it appears in the input
    lemma: str  # Dictionary/root form
    morphology: Optional[str] = None  # Morphological tag string
    sandhi_info: Optional[SandhiInfo] = None  # Sandhi details if applicable
    confidence: float = 1.0  # Engine's confidence (0.0-1.0)
    pos: Optional[str] = None  # Part of speech
    meanings: list[str] = field(default_factory=list)  # Meanings if available
    prakriya: Optional[list[str]] = None  # Derivation steps if available

    def __post_init__(self) -> None:
        """Validate confidence."""
        self.confidence = max(0.0, min(1.0, self.confidence))


@dataclass
class EngineResult:
    """Result from an analysis engine.

    Contains the analyzed segments and metadata about the analysis.
    """

    engine: str  # Name of the engine that produced this result
    segments: list[Segment] = field(default_factory=list)  # Analyzed segments
    confidence: float = 1.0  # Overall confidence in the result
    error: Optional[str] = None  # Error message if analysis failed
    raw_output: Optional[str] = None  # Raw output from engine for debugging

    @property
    def success(self) -> bool:
        """Check if analysis succeeded."""
        return self.error is None and len(self.segments) > 0

    @property
    def segment_count(self) -> int:
        """Number of segments produced."""
        return len(self.segments)

    def __post_init__(self) -> None:
        """Validate confidence."""
        self.confidence = max(0.0, min(1.0, self.confidence))


class EngineBase(ABC):
    """Abstract base class for all analysis engines.

    Each engine must implement the analyze() method to process
    Sanskrit text and return an EngineResult.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Return the engine's unique name."""
        ...

    @property
    def weight(self) -> float:
        """Default weight for ensemble voting. Override in subclasses."""
        return 0.33

    @property
    def is_available(self) -> bool:
        """Check if the engine is available for use.

        Override to implement availability checks (e.g., model loaded).
        """
        return True

    @abstractmethod
    async def analyze(self, text: str) -> EngineResult:
        """Analyze Sanskrit text and return segments.

        Args:
            text: Sanskrit text to analyze (any script).

        Returns:
            EngineResult containing analyzed segments.
        """
        ...

    async def health_check(self) -> bool:
        """Check if the engine is healthy and ready.

        Returns:
            True if engine is ready, False otherwise.
        """
        try:
            result = await self.analyze("राम")
            return result.success
        except Exception:
            return False

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(name={self.name!r}, available={self.is_available})"
