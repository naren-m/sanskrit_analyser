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

    def find_stem(self, slp1_form: str) -> str | None:
        """Try to find a vocabulary stem that *slp1_form* could be inflected from.

        Strips common Sanskrit case-ending suffixes and checks if any
        resulting stem is in the vocabulary.  Returns the matching stem
        or ``None``.
        """
        if self.contains(slp1_form):
            return slp1_form

        # Common nominal case-ending suffixes (most specific first).
        # These cover the most frequent inflectional endings seen in
        # Yoga Sutra compounds / padapāṭha forms.
        _SUFFIXES = (
            "AByAm", "sByAm",  # instrumental/dative/ablative dual
            "AnAm",  # genitive plural
            "asya",  # genitive singular (a-stem)
            "eBya",  # dative/ablative plural
            "ezu",   # locative plural
            "ayoH",  # genitive/locative dual
            "Aya",   # dative singular (a-stem)
            "ena",   # instrumental singular (a-stem)
            "asya",  # genitive singular
            "Am",    # genitive plural / other
            "su",    # locative plural
            "AH",    # nominative plural
            "aH",    # nominative singular (a-stem masc)
            "am",    # accusative singular / nom-acc neuter
            "At",    # ablative singular
            "iH",    # nominative singular (i-stem)
            "yA",    # instrumental singular (i/ī-stem)
            "yoH",   # gen/loc dual
            "In",    # masculine i-stem strong cases
            "e",     # locative singular (a-stem)
            "O",     # nominative/accusative dual
            "A",     # instrumental singular fem, nominative dual neuter
            "m",     # accusative singular
        )

        for suffix in _SUFFIXES:
            if slp1_form.endswith(suffix) and len(slp1_form) > len(suffix):
                stem = slp1_form[: -len(suffix)]
                if self.contains(stem):
                    return stem
                # For a-stem nouns, the stem stored in vocab already
                # ends in 'a', but the inflected form drops it before
                # some suffixes.  Try adding 'a' back.
                if self.contains(stem + "a"):
                    return stem + "a"

        return None

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
    def from_file(cls, path: str | Path) -> Vocabulary:
        """Load vocabulary from a JSON file.

        Args:
            path: Path to a JSON file with a ``words`` array.

        Returns:
            A populated Vocabulary instance.

        Raises:
            FileNotFoundError: If *path* does not exist.
            ValueError: If the JSON is malformed or missing ``words``.
        """
        path = Path(path)
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
            slp1 = entry.get("slp1")
            if not slp1:
                raise ValueError(f"Entry missing 'slp1' key in vocabulary file: {path}")
            words[slp1] = entry
            if entry.get("indeclinable", False):
                indeclinables.add(slp1)

        return cls(words=words, indeclinables=indeclinables)
