"""Script handling for Sanskrit text representations."""

from dataclasses import dataclass
from enum import Enum
from typing import Optional


class Script(Enum):
    """Supported script types for Sanskrit text."""

    DEVANAGARI = "devanagari"
    IAST = "iast"
    SLP1 = "slp1"
    HK = "hk"  # Harvard-Kyoto
    VELTHUIS = "velthuis"
    ITRANS = "itrans"


@dataclass(frozen=True)
class ScriptVariants:
    """Sanskrit text represented in multiple scripts.

    This immutable dataclass holds the same text in Devanagari, IAST, and SLP1
    scripts for flexible display and processing.
    """

    devanagari: str
    iast: str
    slp1: str

    @classmethod
    def from_text(cls, text: str, source_script: Optional[Script] = None) -> "ScriptVariants":
        """Create ScriptVariants from text, auto-detecting script if not specified.

        Args:
            text: The Sanskrit text in any supported script.
            source_script: The script of the input text. If None, auto-detected.

        Returns:
            ScriptVariants with text converted to all three primary scripts.
        """
        from sanskrit_analyzer.utils.transliterate import transliterate
        from sanskrit_analyzer.utils.normalize import detect_script

        if source_script is None:
            source_script = detect_script(text)

        return cls(
            devanagari=transliterate(text, source_script, Script.DEVANAGARI),
            iast=transliterate(text, source_script, Script.IAST),
            slp1=transliterate(text, source_script, Script.SLP1),
        )

    def get(self, script: Script) -> str:
        """Get text in the specified script.

        Args:
            script: The desired output script.

        Returns:
            Text in the specified script.

        Raises:
            ValueError: If script is not one of the three primary scripts.
        """
        if script == Script.DEVANAGARI:
            return self.devanagari
        elif script == Script.IAST:
            return self.iast
        elif script == Script.SLP1:
            return self.slp1
        else:
            raise ValueError(f"ScriptVariants only stores devanagari, iast, slp1. Got: {script}")

    def __str__(self) -> str:
        """Return Devanagari representation by default."""
        return self.devanagari
