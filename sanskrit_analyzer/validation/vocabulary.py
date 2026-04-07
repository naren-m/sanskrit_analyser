"""Vocabulary loader for curated Sanskrit wordlists.

Provides a lookup table of known Sanskrit lemmas (in SLP1 encoding) used to
score and validate sandhi split candidates. The default vocabulary is curated
from the 196 Yoga Sutras of Patanjali.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path


# Default vocabulary file ships with the package
_DEFAULT_VOCAB_PATH = Path(__file__).parent.parent / "data" / "yoga_sutra_vocabulary.json"


@dataclass
class Vocabulary:
    """A curated set of known Sanskrit lemmas keyed by SLP1.

    Attributes:
        words: Mapping from SLP1 lemma to word metadata dict.
        indeclinables: Set of SLP1 lemmas that are indeclinable (avyaya).
    """

    words: dict[str, dict] = field(default_factory=dict)
    indeclinables: set[str] = field(default_factory=set)

    # ------------------------------------------------------------------
    # Lookup methods
    # ------------------------------------------------------------------

    def contains(self, slp1_lemma: str) -> bool:
        """Return True if *slp1_lemma* is in the vocabulary."""
        return slp1_lemma in self.words

    def is_indeclinable(self, slp1_lemma: str) -> bool:
        """Return True if *slp1_lemma* is a known indeclinable (avyaya)."""
        return slp1_lemma in self.indeclinables

    def __len__(self) -> int:
        """Return the number of words in the vocabulary."""
        return len(self.words)

    # ------------------------------------------------------------------
    # Factory methods
    # ------------------------------------------------------------------

    @classmethod
    def load_default(cls) -> Vocabulary:
        """Load the default Yoga Sutra vocabulary shipped with the package."""
        return cls.from_file(_DEFAULT_VOCAB_PATH)

    @classmethod
    def from_file(cls, path: Path) -> Vocabulary:
        """Load vocabulary from a JSON file.

        Args:
            path: Path to a JSON file with a ``words`` array.

        Returns:
            A populated Vocabulary instance.

        Raises:
            FileNotFoundError: If *path* does not exist.
            ValueError: If the JSON is malformed or missing ``words``.
        """
        if not path.exists():
            raise FileNotFoundError(f"Vocabulary file not found: {path}")

        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid JSON in vocabulary file: {path}") from exc

        if "words" not in raw:
            raise ValueError(f"Vocabulary file missing 'words' key: {path}")

        words: dict[str, dict] = {}
        indeclinables: set[str] = set()

        for entry in raw["words"]:
            slp1 = entry["slp1"]
            words[slp1] = entry
            if entry.get("indeclinable", False):
                indeclinables.add(slp1)

        return cls(words=words, indeclinables=indeclinables)
