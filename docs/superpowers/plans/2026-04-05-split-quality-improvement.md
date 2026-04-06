# Split Quality Improvement Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Improve sandhi splitting quality by adding a vocabulary-validated re-scoring layer that generates candidate splits and picks the best one.

**Architecture:** A `SplitValidator` module sits between Vidyut's raw engine output and the tree builder. It generates alternative split candidates by merging/re-splitting Vidyut's segments, scores each candidate against a curated Yoga Sutra vocabulary, and returns the highest-scoring candidate. Indeclinables are protected from splitting entirely.

**Tech Stack:** Python 3.11+, uv for package management, pytest for testing. The `sanskrit_analyzer` library uses `vidyut.cheda` for segmentation and `indic-transliteration` for script conversion.

**Working directory:** `/Users/narenmudivarthy/Projects/sanskrit_analyzer`

**Test command:** `uv run pytest`

---

### Task 1: Create Vocabulary Loader

**Files:**
- Create: `sanskrit_analyzer/validation/__init__.py`
- Create: `sanskrit_analyzer/validation/vocabulary.py`
- Create: `sanskrit_analyzer/data/yoga_sutra_vocabulary.json`
- Test: `tests/test_vocabulary.py`

- [ ] **Step 1: Create the vocabulary data file**

Create `sanskrit_analyzer/data/yoga_sutra_vocabulary.json` with the initial curated vocabulary. These are the most common lemmas from the 196 Yoga Sutras plus essential Sanskrit grammatical words:

```json
{
  "version": "1.0",
  "description": "Curated vocabulary from the 196 Yoga Sutras of Patanjali",
  "words": [
    {"lemma": "yoga", "slp1": "yoga", "type": "noun", "indeclinable": false},
    {"lemma": "atha", "slp1": "aTa", "type": "indeclinable", "indeclinable": true},
    {"lemma": "anuśāsana", "slp1": "anuSAsana", "type": "noun", "indeclinable": false},
    {"lemma": "citta", "slp1": "citta", "type": "noun", "indeclinable": false},
    {"lemma": "vṛtti", "slp1": "vftti", "type": "noun", "indeclinable": false},
    {"lemma": "nirodha", "slp1": "niroDa", "type": "noun", "indeclinable": false},
    {"lemma": "tadā", "slp1": "tadA", "type": "indeclinable", "indeclinable": true},
    {"lemma": "draṣṭṛ", "slp1": "drazwf", "type": "noun", "indeclinable": false},
    {"lemma": "svarūpa", "slp1": "svarUpa", "type": "noun", "indeclinable": false},
    {"lemma": "avasthāna", "slp1": "avasTAna", "type": "noun", "indeclinable": false},
    {"lemma": "sārūpya", "slp1": "sArUpya", "type": "noun", "indeclinable": false},
    {"lemma": "itaratra", "slp1": "itaratra", "type": "indeclinable", "indeclinable": true},
    {"lemma": "pramāṇa", "slp1": "pramARa", "type": "noun", "indeclinable": false},
    {"lemma": "viparyaya", "slp1": "viparyaya", "type": "noun", "indeclinable": false},
    {"lemma": "vikalpa", "slp1": "vikalpa", "type": "noun", "indeclinable": false},
    {"lemma": "nidrā", "slp1": "nidrA", "type": "noun", "indeclinable": false},
    {"lemma": "smṛti", "slp1": "smfti", "type": "noun", "indeclinable": false},
    {"lemma": "abhyāsa", "slp1": "aByAsa", "type": "noun", "indeclinable": false},
    {"lemma": "vairāgya", "slp1": "vErAgya", "type": "noun", "indeclinable": false},
    {"lemma": "sūtra", "slp1": "sUtra", "type": "noun", "indeclinable": false},
    {"lemma": "pratyakṣa", "slp1": "pratyakza", "type": "noun", "indeclinable": false},
    {"lemma": "anumāna", "slp1": "anumAna", "type": "noun", "indeclinable": false},
    {"lemma": "āgama", "slp1": "Agama", "type": "noun", "indeclinable": false},
    {"lemma": "tatra", "slp1": "tatra", "type": "indeclinable", "indeclinable": true},
    {"lemma": "iti", "slp1": "iti", "type": "indeclinable", "indeclinable": true},
    {"lemma": "ca", "slp1": "ca", "type": "indeclinable", "indeclinable": true},
    {"lemma": "tu", "slp1": "tu", "type": "indeclinable", "indeclinable": true},
    {"lemma": "eva", "slp1": "eva", "type": "indeclinable", "indeclinable": true},
    {"lemma": "api", "slp1": "api", "type": "indeclinable", "indeclinable": true},
    {"lemma": "vā", "slp1": "vA", "type": "indeclinable", "indeclinable": true},
    {"lemma": "na", "slp1": "na", "type": "indeclinable", "indeclinable": true},
    {"lemma": "tad", "slp1": "tad", "type": "pronoun", "indeclinable": false},
    {"lemma": "kleśa", "slp1": "kleSa", "type": "noun", "indeclinable": false},
    {"lemma": "karma", "slp1": "karma", "type": "noun", "indeclinable": false},
    {"lemma": "vipāka", "slp1": "vipAka", "type": "noun", "indeclinable": false},
    {"lemma": "āśaya", "slp1": "ASaya", "type": "noun", "indeclinable": false},
    {"lemma": "avidyā", "slp1": "avidyA", "type": "noun", "indeclinable": false},
    {"lemma": "asmitā", "slp1": "asmitA", "type": "noun", "indeclinable": false},
    {"lemma": "rāga", "slp1": "rAga", "type": "noun", "indeclinable": false},
    {"lemma": "dveṣa", "slp1": "dveza", "type": "noun", "indeclinable": false},
    {"lemma": "abhiniveśa", "slp1": "aBiniveSa", "type": "noun", "indeclinable": false},
    {"lemma": "dhyāna", "slp1": "DyAna", "type": "noun", "indeclinable": false},
    {"lemma": "samādhi", "slp1": "samADi", "type": "noun", "indeclinable": false},
    {"lemma": "kaivalya", "slp1": "kEvalya", "type": "noun", "indeclinable": false},
    {"lemma": "sādhana", "slp1": "sADana", "type": "noun", "indeclinable": false},
    {"lemma": "vibhūti", "slp1": "viBUti", "type": "noun", "indeclinable": false},
    {"lemma": "īśvara", "slp1": "ISvara", "type": "noun", "indeclinable": false},
    {"lemma": "praṇidhāna", "slp1": "praRiDAna", "type": "noun", "indeclinable": false},
    {"lemma": "tapas", "slp1": "tapas", "type": "noun", "indeclinable": false},
    {"lemma": "svādhyāya", "slp1": "svADyAya", "type": "noun", "indeclinable": false},
    {"lemma": "puruṣa", "slp1": "puruza", "type": "noun", "indeclinable": false},
    {"lemma": "prakṛti", "slp1": "prakfti", "type": "noun", "indeclinable": false},
    {"lemma": "guṇa", "slp1": "guRa", "type": "noun", "indeclinable": false},
    {"lemma": "sattva", "slp1": "sattva", "type": "noun", "indeclinable": false},
    {"lemma": "rajas", "slp1": "rajas", "type": "noun", "indeclinable": false},
    {"lemma": "tamas", "slp1": "tamas", "type": "noun", "indeclinable": false},
    {"lemma": "prāṇāyāma", "slp1": "prARAyAma", "type": "noun", "indeclinable": false},
    {"lemma": "pratyāhāra", "slp1": "pratyAhAra", "type": "noun", "indeclinable": false},
    {"lemma": "dhāraṇā", "slp1": "DAraRA", "type": "noun", "indeclinable": false},
    {"lemma": "saṃyama", "slp1": "saMyama", "type": "noun", "indeclinable": false},
    {"lemma": "jñāna", "slp1": "jYAna", "type": "noun", "indeclinable": false},
    {"lemma": "viveka", "slp1": "viveka", "type": "noun", "indeclinable": false},
    {"lemma": "khyāti", "slp1": "KyAti", "type": "noun", "indeclinable": false},
    {"lemma": "śraddhā", "slp1": "SradDA", "type": "noun", "indeclinable": false},
    {"lemma": "vīrya", "slp1": "vIrya", "type": "noun", "indeclinable": false},
    {"lemma": "prajñā", "slp1": "prajYA", "type": "noun", "indeclinable": false},
    {"lemma": "samāpatti", "slp1": "samApatti", "type": "noun", "indeclinable": false},
    {"lemma": "vitarka", "slp1": "vitarka", "type": "noun", "indeclinable": false},
    {"lemma": "vicāra", "slp1": "vicAra", "type": "noun", "indeclinable": false},
    {"lemma": "ānanda", "slp1": "Ananda", "type": "noun", "indeclinable": false},
    {"lemma": "yama", "slp1": "yama", "type": "noun", "indeclinable": false},
    {"lemma": "niyama", "slp1": "niyama", "type": "noun", "indeclinable": false},
    {"lemma": "āsana", "slp1": "Asana", "type": "noun", "indeclinable": false},
    {"lemma": "ahiṃsā", "slp1": "ahiMsA", "type": "noun", "indeclinable": false},
    {"lemma": "satya", "slp1": "satya", "type": "noun", "indeclinable": false},
    {"lemma": "asteya", "slp1": "asteya", "type": "noun", "indeclinable": false},
    {"lemma": "brahmacarya", "slp1": "brahmacarya", "type": "noun", "indeclinable": false},
    {"lemma": "aparigraha", "slp1": "aparigraha", "type": "noun", "indeclinable": false},
    {"lemma": "śauca", "slp1": "Sauca", "type": "noun", "indeclinable": false},
    {"lemma": "santoṣa", "slp1": "santoza", "type": "noun", "indeclinable": false},
    {"lemma": "sthira", "slp1": "sTira", "type": "adjective", "indeclinable": false},
    {"lemma": "sukha", "slp1": "suKa", "type": "noun", "indeclinable": false},
    {"lemma": "param", "slp1": "param", "type": "adjective", "indeclinable": false},
    {"lemma": "dṛśya", "slp1": "dfSya", "type": "noun", "indeclinable": false},
    {"lemma": "arthavatva", "slp1": "arTavatva", "type": "noun", "indeclinable": false}
  ]
}
```

- [ ] **Step 2: Write the failing test for vocabulary loading**

Create `tests/test_vocabulary.py`:

```python
"""Tests for the Vocabulary loader."""

import pytest

from sanskrit_analyzer.validation.vocabulary import Vocabulary


class TestVocabulary:
    """Tests for Vocabulary class."""

    def test_load_default_vocabulary(self):
        """Loading the default vocabulary file should succeed."""
        vocab = Vocabulary.load_default()
        assert vocab is not None
        assert len(vocab) > 50

    def test_lookup_known_word(self):
        """Known words should be found by SLP1 key."""
        vocab = Vocabulary.load_default()
        assert vocab.contains("yoga")
        assert vocab.contains("citta")
        assert vocab.contains("niroDa")

    def test_lookup_unknown_word(self):
        """Unknown words should not be found."""
        vocab = Vocabulary.load_default()
        assert not vocab.contains("xyznotaword")

    def test_is_indeclinable(self):
        """Indeclinables should be identified correctly."""
        vocab = Vocabulary.load_default()
        assert vocab.is_indeclinable("aTa")  # atha
        assert vocab.is_indeclinable("iti")
        assert vocab.is_indeclinable("ca")
        assert not vocab.is_indeclinable("yoga")

    def test_empty_vocabulary(self):
        """An empty vocabulary should work without errors."""
        vocab = Vocabulary(words={}, indeclinables=set())
        assert len(vocab) == 0
        assert not vocab.contains("yoga")
        assert not vocab.is_indeclinable("aTa")
```

- [ ] **Step 3: Run the test to verify it fails**

Run: `uv run pytest tests/test_vocabulary.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'sanskrit_analyzer.validation'`

- [ ] **Step 4: Create the validation package and vocabulary loader**

Create `sanskrit_analyzer/validation/__init__.py`:

```python
"""Validation module for split quality improvement."""

from sanskrit_analyzer.validation.vocabulary import Vocabulary
from sanskrit_analyzer.validation.split_validator import SplitValidator

__all__ = ["Vocabulary", "SplitValidator"]
```

Create `sanskrit_analyzer/validation/vocabulary.py`:

```python
"""Curated vocabulary for validating sandhi split quality."""

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)

_DEFAULT_VOCAB_PATH = Path(__file__).parent.parent / "data" / "yoga_sutra_vocabulary.json"


@dataclass
class Vocabulary:
    """A curated vocabulary for scoring sandhi split candidates.

    Words are keyed by their SLP1 form for fast lookup.
    Indeclinables are tracked separately to prevent them from being split.
    """

    words: dict[str, dict] = field(default_factory=dict)
    indeclinables: set[str] = field(default_factory=set)

    def __len__(self) -> int:
        return len(self.words)

    def contains(self, slp1_lemma: str) -> bool:
        """Check if a lemma exists in the vocabulary."""
        return slp1_lemma in self.words

    def is_indeclinable(self, slp1_lemma: str) -> bool:
        """Check if a lemma is a known indeclinable."""
        return slp1_lemma in self.indeclinables

    @classmethod
    def load_default(cls) -> "Vocabulary":
        """Load the default Yoga Sutra vocabulary."""
        return cls.from_file(_DEFAULT_VOCAB_PATH)

    @classmethod
    def from_file(cls, path: Path | str) -> "Vocabulary":
        """Load vocabulary from a JSON file."""
        path = Path(path)
        if not path.exists():
            logger.warning("Vocabulary file not found: %s", path)
            return cls()

        with open(path) as f:
            data = json.load(f)

        words: dict[str, dict] = {}
        indeclinables: set[str] = set()

        for entry in data.get("words", []):
            slp1 = entry["slp1"]
            words[slp1] = entry
            if entry.get("indeclinable", False):
                indeclinables.add(slp1)

        return cls(words=words, indeclinables=indeclinables)
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/test_vocabulary.py -v`
Expected: All 5 tests PASS

- [ ] **Step 6: Commit**

```bash
git add sanskrit_analyzer/validation/ sanskrit_analyzer/data/yoga_sutra_vocabulary.json tests/test_vocabulary.py
git commit -m "feat: add curated vocabulary loader for split validation"
```

---

### Task 2: Create Split Validator with Candidate Generation and Scoring

**Files:**
- Create: `sanskrit_analyzer/validation/split_validator.py`
- Test: `tests/test_split_validator.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_split_validator.py`:

```python
"""Tests for the SplitValidator."""

import pytest

from sanskrit_analyzer.engines.base import Segment
from sanskrit_analyzer.validation.split_validator import SplitValidator
from sanskrit_analyzer.validation.vocabulary import Vocabulary


@pytest.fixture
def vocab() -> Vocabulary:
    """Load the default vocabulary."""
    return Vocabulary.load_default()


@pytest.fixture
def validator(vocab: Vocabulary) -> SplitValidator:
    """Create a SplitValidator with default vocabulary."""
    return SplitValidator(vocab)


class TestIndeclinableProtection:
    """Indeclinables should not be split."""

    def test_atha_not_split(self, validator: SplitValidator):
        """atha (SLP1: aTa) should remain unsplit."""
        bad_segments = [
            Segment(surface="at", lemma="ad", confidence=0.9),
            Segment(surface="ha", lemma="ha", confidence=0.9),
        ]
        result = validator.validate_and_rescore(bad_segments, "aTa")
        assert len(result) == 1
        assert result[0].surface == "aTa"

    def test_iti_not_split(self, validator: SplitValidator):
        """iti should remain unsplit."""
        bad_segments = [
            Segment(surface="i", lemma="i", confidence=0.9),
            Segment(surface="ti", lemma="ti", confidence=0.9),
        ]
        result = validator.validate_and_rescore(bad_segments, "iti")
        assert len(result) == 1
        assert result[0].surface == "iti"


class TestCandidateGeneration:
    """Candidate generation should produce better alternatives."""

    def test_yogasutra_corrected(self, validator: SplitValidator):
        """yogasutra should split as yoga + sutra, not yogas + ut + ra."""
        bad_segments = [
            Segment(surface="yogas", lemma="yuj", confidence=0.9),
            Segment(surface="ut", lemma="u", confidence=0.9),
            Segment(surface="ra", lemma="ra", confidence=0.9),
        ]
        result = validator.validate_and_rescore(bad_segments, "yogasutra")
        lemmas = [s.lemma for s in result]
        assert "yoga" in lemmas or "yuj" in lemmas
        # Should not have single-char junk
        assert not any(len(s.surface) == 1 for s in result)

    def test_single_valid_word_not_split(self, validator: SplitValidator):
        """A single word that's in the vocabulary should stay unsplit."""
        segments = [
            Segment(surface="yoga", lemma="yoga", confidence=0.9),
        ]
        result = validator.validate_and_rescore(segments, "yoga")
        assert len(result) == 1
        assert result[0].surface == "yoga"


class TestScoring:
    """Scoring should prefer vocabulary-matched segments."""

    def test_vocab_match_scores_higher(self, validator: SplitValidator):
        """A candidate with vocabulary matches should score higher than one without."""
        # Candidate 1: bad split (no vocab matches)
        bad = [
            Segment(surface="yogas", lemma="yuj", confidence=0.9),
            Segment(surface="ut", lemma="u", confidence=0.9),
            Segment(surface="ra", lemma="ra", confidence=0.9),
        ]
        # Candidate 2: good split (vocab matches)
        good = [
            Segment(surface="yoga", lemma="yoga", confidence=0.9),
            Segment(surface="sUtra", lemma="sUtra", confidence=0.9),
        ]
        bad_score = validator.score_candidate(bad)
        good_score = validator.score_candidate(good)
        assert good_score > bad_score

    def test_single_char_penalized(self, validator: SplitValidator):
        """Single-character segments should be penalized."""
        with_junk = [
            Segment(surface="yogas", lemma="yuj", confidence=0.9),
            Segment(surface="u", lemma="u", confidence=0.9),
        ]
        without_junk = [
            Segment(surface="yogasu", lemma="yogasu", confidence=0.9),
        ]
        assert validator.score_candidate(without_junk) > validator.score_candidate(with_junk)


class TestPassthrough:
    """When no better candidate exists, pass through original."""

    def test_no_vocabulary_passthrough(self):
        """With empty vocabulary, original segments pass through unchanged."""
        empty_vocab = Vocabulary(words={}, indeclinables=set())
        validator = SplitValidator(empty_vocab)
        segments = [
            Segment(surface="unknown", lemma="unknown", confidence=0.9),
        ]
        result = validator.validate_and_rescore(segments, "unknown")
        assert len(result) == 1
        assert result[0].surface == "unknown"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_split_validator.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'sanskrit_analyzer.validation.split_validator'`

- [ ] **Step 3: Implement the SplitValidator**

Create `sanskrit_analyzer/validation/split_validator.py`:

```python
"""Split validator: generates candidate splits and scores them against vocabulary."""

import logging
from dataclasses import dataclass

from sanskrit_analyzer.engines.base import Segment
from sanskrit_analyzer.validation.vocabulary import Vocabulary

logger = logging.getLogger(__name__)

# Scoring weights
VOCAB_MATCH_SCORE = 2.0
INDECLINABLE_SCORE = 3.0
MORPHOLOGY_SCORE = 1.0
SINGLE_CHAR_PENALTY = -2.0
UNKNOWN_PENALTY = -1.0
SIMPLICITY_BONUS = 0.5

MAX_CANDIDATES = 20


@dataclass
class ScoredCandidate:
    """A candidate split with its score."""

    segments: list[Segment]
    score: float


class SplitValidator:
    """Validates and re-scores sandhi splits using a curated vocabulary.

    Takes Vidyut's raw segments, generates alternative split candidates
    by merging and re-splitting, scores each against the vocabulary,
    and returns the best-scoring candidate.
    """

    def __init__(self, vocabulary: Vocabulary) -> None:
        self._vocab = vocabulary

    def validate_and_rescore(
        self,
        segments: list[Segment],
        original_slp1: str,
    ) -> list[Segment]:
        """Validate segments and return the best-scoring split.

        Args:
            segments: Raw segments from Vidyut.
            original_slp1: The original input text in SLP1.

        Returns:
            The best-scoring list of segments.
        """
        if not segments:
            return segments

        # Check if the entire input is an indeclinable
        if self._vocab.is_indeclinable(original_slp1):
            return [Segment(
                surface=original_slp1,
                lemma=original_slp1,
                confidence=1.0,
            )]

        # Generate candidates
        candidates = self._generate_candidates(segments, original_slp1)

        if not candidates:
            return segments

        # Score and pick the best
        scored = [
            ScoredCandidate(segments=c, score=self.score_candidate(c))
            for c in candidates
        ]
        scored.sort(key=lambda sc: (-sc.score, len(sc.segments)))

        best = scored[0]
        if best.segments != segments:
            logger.debug(
                "Re-scored split: %s -> %s (score: %.1f)",
                [s.surface for s in segments],
                [s.surface for s in best.segments],
                best.score,
            )

        return best.segments

    def score_candidate(self, segments: list[Segment]) -> float:
        """Score a candidate split against the vocabulary.

        Args:
            segments: The candidate segments.

        Returns:
            Numerical score (higher is better).
        """
        if not segments:
            return 0.0

        score = 0.0
        max_segments = max(len(segments), 1)

        for seg in segments:
            lemma = seg.lemma or seg.surface

            if self._vocab.is_indeclinable(lemma):
                score += INDECLINABLE_SCORE
            elif self._vocab.contains(lemma):
                score += VOCAB_MATCH_SCORE
            elif self._vocab.contains(seg.surface):
                score += VOCAB_MATCH_SCORE
            elif seg.pos is not None:
                score += MORPHOLOGY_SCORE
            else:
                score += UNKNOWN_PENALTY

            if len(seg.surface) == 1:
                score += SINGLE_CHAR_PENALTY

        # Simplicity bonus: fewer segments is better
        score += SIMPLICITY_BONUS * (max_segments - len(segments))

        return score

    def _generate_candidates(
        self,
        segments: list[Segment],
        original_slp1: str,
    ) -> list[list[Segment]]:
        """Generate alternative split candidates.

        Strategies:
        1. Include the original Vidyut split
        2. Include the unsplit (full merge) as a candidate
        3. Merge adjacent pairs and re-split at vocabulary-matching positions
        4. For unsplit input, try splitting at every position

        Args:
            segments: Original segments from Vidyut.
            original_slp1: The original input in SLP1.

        Returns:
            List of candidate segment lists, capped at MAX_CANDIDATES.
        """
        candidates: list[list[Segment]] = []

        # Always include original
        candidates.append(segments)

        # Candidate: unsplit (whole string as one segment)
        candidates.append([Segment(
            surface=original_slp1,
            lemma=original_slp1,
            confidence=0.5,
        )])

        # Merge adjacent segments and try re-splitting
        if len(segments) >= 2:
            candidates.extend(
                self._merge_and_resplit(segments, original_slp1)
            )

        # For single-segment input (unsplit compound), try splitting
        if len(segments) == 1:
            candidates.extend(
                self._split_single_segment(original_slp1)
            )

        # Deduplicate and cap
        seen: set[str] = set()
        unique: list[list[Segment]] = []
        for candidate in candidates:
            key = "|".join(s.surface for s in candidate)
            if key not in seen:
                seen.add(key)
                unique.append(candidate)

        return unique[:MAX_CANDIDATES]

    def _merge_and_resplit(
        self,
        segments: list[Segment],
        original_slp1: str,
    ) -> list[list[Segment]]:
        """Merge adjacent segments and try re-splitting at vocab boundaries.

        Args:
            segments: Original segments.
            original_slp1: Full original string.

        Returns:
            List of alternative candidate splits.
        """
        candidates: list[list[Segment]] = []

        # Try merging all segments and re-splitting from the full string
        candidates.extend(self._split_single_segment(original_slp1))

        # Try merging pairs of adjacent segments
        for i in range(len(segments) - 1):
            merged_surface = segments[i].surface + segments[i + 1].surface
            before = segments[:i]
            after = segments[i + 2:]

            # Try splitting the merged pair at each position
            for pos in range(1, len(merged_surface)):
                left = merged_surface[:pos]
                right = merged_surface[pos:]

                if self._vocab.contains(left) or self._vocab.contains(right):
                    new_segments = (
                        list(before)
                        + [Segment(surface=left, lemma=left, confidence=0.8)]
                        + [Segment(surface=right, lemma=right, confidence=0.8)]
                        + list(after)
                    )
                    candidates.append(new_segments)

        return candidates

    def _split_single_segment(
        self,
        text: str,
    ) -> list[list[Segment]]:
        """Try splitting a single string at positions that match vocabulary.

        Uses a greedy left-to-right scan: at each position, find the longest
        prefix that matches the vocabulary, consume it, and repeat.

        Args:
            text: The SLP1 string to split.

        Returns:
            List of candidate splits where at least one part matches vocab.
        """
        candidates: list[list[Segment]] = []

        # Greedy longest-match from left
        greedy_result = self._greedy_vocab_split(text)
        if greedy_result and len(greedy_result) > 1:
            candidates.append(greedy_result)

        # Also try all two-way splits where at least one half matches
        for pos in range(1, len(text)):
            left = text[:pos]
            right = text[pos:]

            if self._vocab.contains(left) or self._vocab.contains(right):
                candidate = [
                    Segment(surface=left, lemma=left, confidence=0.8),
                    Segment(surface=right, lemma=right, confidence=0.8),
                ]
                candidates.append(candidate)

                # Recursively try splitting the non-matching half
                if self._vocab.contains(left) and len(right) > 2:
                    sub_splits = self._greedy_vocab_split(right)
                    if sub_splits and len(sub_splits) >= 1:
                        full = [Segment(surface=left, lemma=left, confidence=0.8)] + sub_splits
                        candidates.append(full)

                if self._vocab.contains(right) and len(left) > 2:
                    sub_splits = self._greedy_vocab_split(left)
                    if sub_splits and len(sub_splits) >= 1:
                        full = sub_splits + [Segment(surface=right, lemma=right, confidence=0.8)]
                        candidates.append(full)

        return candidates

    def _greedy_vocab_split(self, text: str) -> list[Segment]:
        """Greedy longest-first vocabulary-based split.

        Args:
            text: SLP1 text to split.

        Returns:
            List of segments from greedy matching. May include
            unmatched remainders as single segments.
        """
        result: list[Segment] = []
        pos = 0

        while pos < len(text):
            # Try longest prefix first
            best_len = 0
            for end in range(len(text), pos, -1):
                candidate = text[pos:end]
                if self._vocab.contains(candidate):
                    best_len = end - pos
                    break

            if best_len > 0:
                word = text[pos : pos + best_len]
                result.append(Segment(surface=word, lemma=word, confidence=0.8))
                pos += best_len
            else:
                # No vocab match - consume one character and keep going
                # (this will be penalized by scoring)
                remaining = text[pos:]
                result.append(Segment(surface=remaining, lemma=remaining, confidence=0.3))
                break

        return result
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_split_validator.py -v`
Expected: All 7 tests PASS

- [ ] **Step 5: Run all existing tests to check for regressions**

Run: `uv run pytest`
Expected: All 380+ tests PASS

- [ ] **Step 6: Commit**

```bash
git add sanskrit_analyzer/validation/split_validator.py tests/test_split_validator.py
git commit -m "feat: add SplitValidator with candidate generation and scoring"
```

---

### Task 3: Wire SplitValidator into Analyzer Pipeline

**Files:**
- Modify: `sanskrit_analyzer/analyzer.py:131-154` (in `_initialize`) and `sanskrit_analyzer/analyzer.py:326-336` (in `analyze`)
- Test: `tests/test_golden_splits.py`
- Create: `tests/data/yoga_sutra_splits_golden.json`

- [ ] **Step 1: Create the golden test data file**

Create `tests/data/yoga_sutra_splits_golden.json`:

```json
[
  {"input": "atha", "expected_lemmas": ["aTa"]},
  {"input": "iti", "expected_lemmas": ["iti"]},
  {"input": "ca", "expected_lemmas": ["ca"]},
  {"input": "eva", "expected_lemmas": ["eva"]},
  {"input": "yoga", "expected_lemmas": ["yoga"]},
  {"input": "citta", "expected_lemmas": ["citta"]},
  {"input": "yogasutra", "input_slp1": "yogasUtra", "expected_lemmas": ["yoga", "sUtra"]}
]
```

Note: Start with a small set of high-confidence test cases. Expand as the validator improves.

- [ ] **Step 2: Write the golden split test**

Create `tests/test_golden_splits.py`:

```python
"""Golden tests for sandhi split quality.

These tests verify that the Analyzer produces correct splits
for known Yoga Sutra compounds. They use the real Analyzer
with all engines, so they require vidyut to be installed.
"""

import json
from pathlib import Path

import pytest

from sanskrit_analyzer import Analyzer, Config, AnalysisMode

GOLDEN_FILE = Path(__file__).parent / "data" / "yoga_sutra_splits_golden.json"


def load_golden_cases() -> list[dict]:
    """Load golden test cases from JSON file."""
    with open(GOLDEN_FILE) as f:
        return json.load(f)


@pytest.fixture(scope="module")
def analyzer() -> Analyzer:
    """Create a shared Analyzer instance (expensive to initialize)."""
    try:
        return Analyzer(Config())
    except Exception:
        pytest.skip("Analyzer not available (vidyut not installed)")


@pytest.mark.parametrize(
    "case",
    load_golden_cases(),
    ids=[c["input"] for c in load_golden_cases()],
)
@pytest.mark.asyncio
async def test_golden_split(analyzer: Analyzer, case: dict):
    """Verify that the analyzer produces the expected split."""
    input_text = case.get("input_slp1", case["input"])
    expected_lemmas = case["expected_lemmas"]

    result = await analyzer.analyze(input_text, mode=AnalysisMode.EDUCATIONAL)

    if not result.parse_forest:
        pytest.skip(f"No parse result for {input_text}")

    actual_lemmas = [
        w.lemma
        for sg in result.parse_forest[0].sandhi_groups
        for w in sg.base_words
    ]

    assert actual_lemmas == expected_lemmas, (
        f"Split mismatch for '{case['input']}':\n"
        f"  Expected: {expected_lemmas}\n"
        f"  Actual:   {actual_lemmas}"
    )
```

- [ ] **Step 3: Run golden tests to see current failures**

Run: `uv run pytest tests/test_golden_splits.py -v`
Expected: Some tests FAIL (especially `atha`, `yogasutra`) — this is the baseline before wiring in the validator.

- [ ] **Step 4: Wire SplitValidator into Analyzer._initialize()**

In `sanskrit_analyzer/analyzer.py`, add the import at the top (after existing imports around line 32):

```python
from sanskrit_analyzer.validation.split_validator import SplitValidator
from sanskrit_analyzer.validation.vocabulary import Vocabulary
```

In `_initialize()` method (around line 151, after `self._tree_builder = TreeBuilder(TreeBuilderConfig())`), add:

```python
        # Initialize split validator with curated vocabulary
        try:
            vocab = Vocabulary.load_default()
            self._split_validator = SplitValidator(vocab)
            logger.info("Split validator loaded with %d vocabulary entries", len(vocab))
        except Exception as e:
            logger.warning("Split validator not available: %s", e)
            self._split_validator = None
```

Also add `self._split_validator: SplitValidator | None = None` to `__init__` (around line 95, after `self._dhatu_db`).

- [ ] **Step 5: Wire SplitValidator into the analyze() method**

In the `analyze()` method (around line 328-336), change the ensemble result handling to validate segments before building the tree. Replace:

```python
        ensemble_result = await self._ensemble.analyze(normalized_slp1)

        # Restore engines if we filtered
        if engines:
            self._ensemble._engines = original_engines

        # Build parse tree
        assert self._tree_builder is not None
        tree = self._tree_builder.build(
            ensemble_result,
            original_text,
            normalized_slp1,
            mode.value,
        )
```

With:

```python
        ensemble_result = await self._ensemble.analyze(normalized_slp1)

        # Restore engines if we filtered
        if engines:
            self._ensemble._engines = original_engines

        # Validate and re-score splits if validator is available
        if self._split_validator and ensemble_result.segments:
            validated_segments = self._split_validator.validate_and_rescore(
                ensemble_result.segments,
                normalized_slp1,
            )
            # Build tree from validated segments (single-engine path)
            assert self._tree_builder is not None
            tree = self._tree_builder.build_from_segments(
                validated_segments,
                original_text,
                normalized_slp1,
                engine_name="vidyut+validator",
                mode=mode.value,
            )
        else:
            # Build parse tree from ensemble (original path)
            assert self._tree_builder is not None
            tree = self._tree_builder.build(
                ensemble_result,
                original_text,
                normalized_slp1,
                mode.value,
            )
```

- [ ] **Step 6: Run golden tests to verify improvement**

Run: `uv run pytest tests/test_golden_splits.py -v`
Expected: More tests PASS than before (especially `atha`, indeclinables)

- [ ] **Step 7: Run all tests to check for regressions**

Run: `uv run pytest`
Expected: All 380+ existing tests PASS, plus new golden tests

- [ ] **Step 8: Commit**

```bash
git add sanskrit_analyzer/analyzer.py tests/test_golden_splits.py tests/data/yoga_sutra_splits_golden.json
git commit -m "feat: wire SplitValidator into Analyzer pipeline"
```

---

### Task 4: Iterate on Vocabulary and Golden Tests

**Files:**
- Modify: `sanskrit_analyzer/data/yoga_sutra_vocabulary.json`
- Modify: `tests/data/yoga_sutra_splits_golden.json`

- [ ] **Step 1: Test more Yoga Sutra compounds**

Run the analyzer on real sutra words to identify gaps in the vocabulary:

```bash
uv run python -c "
import asyncio
from sanskrit_analyzer import Analyzer, Config, AnalysisMode

async def test_splits():
    a = Analyzer(Config())
    words = ['yogAnuSAsanam', 'yogaScittavfttiNiroDaH', 'aByAsavErAgyAByAm',
             'pratyakzAnumAnAgamAH', 'vfttisBrUpyam', 'tadA']
    for w in words:
        r = await a.analyze(w, mode=AnalysisMode.EDUCATIONAL)
        if r.parse_forest:
            lemmas = [bw.lemma for sg in r.parse_forest[0].sandhi_groups for bw in sg.base_words]
            print(f'{w}: {lemmas}')
        else:
            print(f'{w}: NO PARSE')

asyncio.run(test_splits())
"
```

- [ ] **Step 2: Add missing lemmas to vocabulary**

Based on the test results, add any missing lemmas to `sanskrit_analyzer/data/yoga_sutra_vocabulary.json`. Focus on words that appear in the 196 sutras.

- [ ] **Step 3: Expand golden test cases**

Add more test cases to `tests/data/yoga_sutra_splits_golden.json` for compounds that now split correctly. Only add cases where you have verified the correct split.

- [ ] **Step 4: Run all tests**

Run: `uv run pytest`
Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
git add sanskrit_analyzer/data/yoga_sutra_vocabulary.json tests/data/yoga_sutra_splits_golden.json
git commit -m "feat: expand vocabulary and golden tests for Yoga Sutra compounds"
```

---

### Task 5: Update Yoga Sutras Dependency

**Files:**
- Modify: `/Users/narenmudivarthy/Projects/yoga_sutras/backend/requirements.txt`

**Working directory:** `/Users/narenmudivarthy/Projects/yoga_sutras`

- [ ] **Step 1: Reinstall sanskrit_analyzer from local source**

```bash
cd /Users/narenmudivarthy/Projects/yoga_sutras/backend
source venv/bin/activate
pip install -e /Users/narenmudivarthy/Projects/sanskrit_analyzer
```

- [ ] **Step 2: Test the improved splits via the yoga_sutras API locally**

```bash
cd /Users/narenmudivarthy/Projects/yoga_sutras/backend
source venv/bin/activate
python -c "
from app.services.sanskrit_adapter import get_sanskrit_adapter
adapter = get_sanskrit_adapter()
for word in ['yogasutra', 'atha', 'yogānuśāsanam']:
    result = adapter.split(word)
    splits = [(s['text'], s['lemma']) for s in result['splits']]
    print(f'{word}: {splits}')
"
```

Expected: Better splits than before (yoga+sutra, atha unsplit, etc.)

- [ ] **Step 3: Commit**

```bash
git add backend/requirements.txt
git commit -m "feat: update sanskrit_analyzer for improved split quality"
```
