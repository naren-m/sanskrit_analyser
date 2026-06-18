"""Split validator with candidate generation and scoring.

Takes Vidyut's raw segments + original SLP1 string, generates candidate
splits, scores them against the vocabulary, and returns the best candidate.
"""

from __future__ import annotations

from sanskrit_analyzer.engines.base import Segment
from sanskrit_analyzer.validation.vocabulary import Vocabulary

# Maximum number of candidates to evaluate
_MAX_CANDIDATES = 40

# Common vowel sandhi rules (SLP1 encoding).
# Maps a fused character to possible (left_ending, right_beginning) pairs.
_VOWEL_SANDHI: dict[str, list[tuple[str, str]]] = {
    "A": [("a", "a"), ("a", "A"), ("A", "a"), ("A", "A")],
    "I": [("i", "i"), ("i", "I"), ("I", "i"), ("I", "I")],
    "U": [("u", "u"), ("u", "U"), ("U", "u"), ("U", "U")],
    "e": [("a", "i"), ("a", "I")],
    "o": [("a", "u"), ("a", "U")],
    "E": [("a", "e"), ("a", "E")],
    "O": [("a", "o"), ("a", "O")],
}


class SplitValidator:
    """Validates and re-scores sandhi split candidates.

    Given raw segments from an engine (e.g. Vidyut) and the original SLP1
    input, the validator:
      1. Checks if the input is an indeclinable (returns it unsplit).
      2. Generates candidate splits by merging / re-splitting segments.
      3. Scores each candidate against the vocabulary.
      4. Returns the best-scoring candidate.
    """

    def __init__(self, vocabulary: Vocabulary, word_guard: object | None = None) -> None:
        """Initialize the validator.

        Args:
            vocabulary: The curated scoring vocabulary.
            word_guard: Optional real-word veto (e.g. ``KoshaVocabulary``). Any
                object exposing a de-sandhi-aware ``contains(surface) -> bool``.
                When provided, the validator will NEVER emit a candidate that
                splits a token the guard recognises as a valid whole word.
        """
        self._vocab = vocabulary
        self._word_guard = word_guard

    # ------------------------------------------------------------------

    # Minimum SLP1 length for a token to be lockable. The kosha recognises
    # 1-2 char particles/fragments (a, i, u, na, ca, am, ...), so locking those
    # would freeze them in place and could ENTRENCH a cheda over-split (e.g.
    # blocking the desired merge "van" + "am" -> "vanam"). Only tokens long
    # enough to be a "real word worth protecting" are locked.
    _MIN_LOCK_LEN = 3

    def _is_locked(self, surface: str) -> bool:
        """Return True if *surface* is a real whole word that must not be split.

        A "locked" token is a sufficiently long surface that the kosha
        word-guard recognises. Such tokens are real Sanskrit words (e.g.
        "gacCati", "yoga", "duHKa") and must stay whole; the validator may
        still merge fragments and split non-words. Short tokens (< 3 SLP1
        chars) are never locked so cheda over-splits can still be merged back.
        """
        if self._word_guard is None or not surface:
            return False
        if len(surface) < self._MIN_LOCK_LEN:
            return False
        try:
            return bool(self._word_guard.contains(surface))
        except Exception:
            return False

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def validate_and_rescore(
        self,
        segments: list[Segment],
        original_slp1: str,
    ) -> list[Segment]:
        """Validate *segments* and return the best-scoring candidate split.

        Args:
            segments: Raw segments produced by an analysis engine.
            original_slp1: The original unsplit input in SLP1 encoding.

        Returns:
            The best-scoring list of segments.
        """
        if not segments and not original_slp1:
            return []

        # 1. Indeclinable shortcut -- never split these
        if self._vocab.is_indeclinable(original_slp1):
            return [Segment(surface=original_slp1, lemma=original_slp1, pos="indeclinable")]

        # 2. Generate candidates
        candidates = self._generate_candidates(segments, original_slp1)

        if not candidates:
            return segments  # fallback

        # 3. Score and pick the best
        max_seg_count = max(len(c) for c in candidates)
        best = max(candidates, key=lambda c: self.score_candidate(c, max_seg_count))
        return best

    def score_candidate(
        self, segments: list[Segment], max_segments: int | None = None
    ) -> float:
        """Score a candidate split.

        Scoring signals:
          +2.0  segment lemma found in vocabulary
          +3.0  segment is a known indeclinable
          +1.0  segment has valid morphological data (pos is not None)
          -2.0  segment is a single character
          -1.0  segment lemma not found anywhere
          +0.5  per reduction vs max segment count (simplicity bonus)

        Args:
            segments: The candidate segments to score.
            max_segments: Maximum segment count across all candidates being
                compared. When ``None`` (standalone usage), the simplicity
                bonus is zero.
        """
        if not segments:
            return -100.0

        ref = max_segments if max_segments is not None else len(segments)
        score = 0.0

        for seg in segments:
            lemma = seg.lemma

            if self._vocab.is_indeclinable(lemma):
                score += 3.0
            elif self._vocab.contains(lemma):
                score += 2.0
            elif self._vocab.find_stem(seg.surface) is not None:
                # Surface form is an inflected form of a known word
                score += 1.5
            else:
                score -= 1.0

            if seg.pos is not None:
                score += 1.0

            if len(seg.surface) == 1:
                score -= 2.0

        # Simplicity bonus: fewer segments is better. Clamp it so it can
        # never outweigh a correctly-scored split (real lemmas score +2 each).
        simplicity_bonus = (ref - len(segments)) * 0.5
        simplicity_bonus = min(simplicity_bonus, 1.0)
        score += simplicity_bonus

        return score

    # ------------------------------------------------------------------
    # Candidate generation (private)
    # ------------------------------------------------------------------

    def _generate_candidates(
        self,
        segments: list[Segment],
        original_slp1: str,
    ) -> list[list[Segment]]:
        """Generate candidate splits.

        Strategy:
          1. Always include the original Vidyut split.
          2. Include the unsplit (whole string as one segment).
          3. Merge adjacent pairs and try re-splitting.
          4. For single-segment input, try splitting at every position
             with greedy longest-match.
        """
        candidates: list[list[Segment]] = []
        seen: set[tuple[str, ...]] = set()

        # Real-word veto: cheda's authoritative tokens that are valid whole
        # kosha words must never be broken apart by any candidate. (Merging
        # fragments into a real word is still fine.)
        locked_tokens = [
            seg.surface for seg in segments if self._is_locked(seg.surface)
        ]

        def _breaks_locked(segs: list[Segment]) -> bool:
            surfaces = {s.surface for s in segs}
            return any(tok not in surfaces for tok in locked_tokens)

        def _add(segs: list[Segment]) -> None:
            if _breaks_locked(segs):
                return
            key = tuple(s.surface for s in segs)
            if key not in seen and len(candidates) < _MAX_CANDIDATES:
                seen.add(key)
                candidates.append(segs)

        # 1. Original split
        if segments:
            _add(segments)

        # 2. Unsplit -- whole string as one segment.
        # Do NOT emit the whole-string candidate when the input spans multiple
        # words (contains a space): a multi-word line is never a single token,
        # and emitting it lets the simplicity bonus collapse correct splits.
        if original_slp1 and " " not in original_slp1:
            _add([self._make_segment(original_slp1)])

        # 3. Merge adjacent pairs and re-split
        if len(segments) >= 2:
            self._merge_and_resplit(segments, _add)

        # 4. For single-segment or unsplit input, try positional splits
        if original_slp1 and len(original_slp1) >= 2:
            self._try_positional_splits(original_slp1, _add)

        return candidates

    def _merge_and_resplit(
        self,
        segments: list[Segment],
        add_fn: callable,
    ) -> None:
        """Merge each adjacent pair, then try re-splitting the merged string."""
        for i in range(len(segments) - 1):
            merged_surface = segments[i].surface + segments[i + 1].surface

            # Keep the other segments intact, replace pair with merged
            prefix = segments[:i]
            suffix = segments[i + 2 :]

            # Option A: just merge (don't split the merged piece)
            merged_seg = self._make_segment(merged_surface)
            add_fn(prefix + [merged_seg] + suffix)

            # Option B: try splitting the merged piece at every position
            for j in range(1, len(merged_surface)):
                left_str = merged_surface[:j]
                right_str = merged_surface[j:]

                left_in_vocab = self._vocab.contains(left_str)
                right_in_vocab = self._vocab.contains(right_str)

                if left_in_vocab or right_in_vocab:
                    left_seg = self._make_segment(left_str)
                    right_seg = self._make_segment(right_str)
                    add_fn(prefix + [left_seg, right_seg] + suffix)

    def _try_positional_splits(
        self,
        text: str,
        add_fn: callable,
    ) -> None:
        """Try splitting *text* at every position using greedy longest-match."""
        # Real-word veto: if the whole token is a valid kosha word, it must stay
        # whole. Emit NO split candidates for it (not even sandhi splits). This
        # is what keeps "gacCati" and single golden words ("yoga", "duHKa")
        # intact. cheda already pre-splits multi-word input, so individual
        # tokens are still segmented upstream.
        if self._is_locked(text):
            return

        # Try simple 2-way splits where at least one side is in vocab
        for i in range(1, len(text)):
            left_str = text[:i]
            right_str = text[i:]

            left_in_vocab = self._vocab.contains(left_str)
            right_in_vocab = self._vocab.contains(right_str)

            if left_in_vocab or right_in_vocab:
                left_seg = self._make_segment(left_str)
                right_seg = self._make_segment(right_str)
                add_fn([left_seg, right_seg])

            # Also check if either side is an inflected form
            if not (left_in_vocab or right_in_vocab):
                left_stem = self._vocab.find_stem(left_str)
                right_stem = self._vocab.find_stem(right_str)
                if left_stem is not None or right_stem is not None:
                    left_seg = self._make_segment(left_str)
                    right_seg = self._make_segment(right_str)
                    add_fn([left_seg, right_seg])

        # Try sandhi-aware splits
        self._try_sandhi_splits(text, add_fn)

        # Greedy longest-match from left
        greedy = self._greedy_split(text)
        if greedy and len(greedy) > 1:
            add_fn(greedy)

    def _try_sandhi_splits(
        self,
        text: str,
        add_fn: callable,
    ) -> None:
        """Try splitting *text* by reversing common vowel sandhi rules.

        At each position, if the character is a sandhi product, try
        expanding it back into separate endings/beginnings and check
        if the resulting parts are in the vocabulary.
        """
        for i in range(1, len(text)):
            fused_char = text[i - 1]
            replacements = _VOWEL_SANDHI.get(fused_char)
            if not replacements:
                continue

            prefix = text[: i - 1]  # everything before the fused char
            suffix = text[i:]  # everything after the fused char

            for left_end, right_begin in replacements:
                left_str = prefix + left_end
                right_str = right_begin + suffix

                left_ok = (
                    self._vocab.contains(left_str)
                    or self._vocab.find_stem(left_str) is not None
                )
                right_ok = (
                    self._vocab.contains(right_str)
                    or self._vocab.find_stem(right_str) is not None
                )

                if left_ok and right_ok:
                    left_seg = self._make_segment(left_str)
                    right_seg = self._make_segment(right_str)
                    add_fn([left_seg, right_seg])

    def _greedy_split(self, text: str) -> list[Segment]:
        """Split *text* using greedy longest-match against the vocabulary."""
        result: list[Segment] = []
        pos = 0

        while pos < len(text):
            best_end = pos + 1  # at least consume one character
            # Try longest match first
            for end in range(len(text), pos, -1):
                candidate = text[pos:end]
                if self._vocab.contains(candidate):
                    best_end = end
                    break

            seg_text = text[pos:best_end]
            result.append(self._make_segment(seg_text))
            pos = best_end

        return result

    def _make_segment(self, surface: str) -> Segment:
        """Create a Segment for *surface*, enriching with vocab data if available."""
        lemma = surface
        pos: str | None = None

        if self._vocab.is_indeclinable(surface):
            pos = "indeclinable"
        elif self._vocab.contains(surface):
            entry = self._vocab.words.get(surface, {})
            pos = entry.get("type")
        else:
            # Try to find a vocabulary stem for an inflected form
            stem = self._vocab.find_stem(surface)
            if stem is not None:
                lemma = stem
                entry = self._vocab.words.get(stem, {})
                pos = entry.get("type")

        return Segment(surface=surface, lemma=lemma, pos=pos)
