"""Split validator with candidate generation and scoring.

Takes Vidyut's raw segments + original SLP1 string, generates candidate
splits, scores them against the vocabulary, and returns the best candidate.
"""

from __future__ import annotations

from sanskrit_analyzer.engines.base import Segment
from sanskrit_analyzer.validation.vocabulary import Vocabulary

# Maximum number of candidates to evaluate
_MAX_CANDIDATES = 20


class SplitValidator:
    """Validates and re-scores sandhi split candidates.

    Given raw segments from an engine (e.g. Vidyut) and the original SLP1
    input, the validator:
      1. Checks if the input is an indeclinable (returns it unsplit).
      2. Generates candidate splits by merging / re-splitting segments.
      3. Scores each candidate against the vocabulary.
      4. Returns the best-scoring candidate.
    """

    def __init__(self, vocabulary: Vocabulary) -> None:
        self._vocab = vocabulary

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
        best = max(candidates, key=self.score_candidate)
        return best

    def score_candidate(self, segments: list[Segment]) -> float:
        """Score a candidate split.

        Scoring signals:
          +2.0  segment lemma found in vocabulary
          +3.0  segment is a known indeclinable
          +1.0  segment has valid morphological data (pos is not None)
          -2.0  segment is a single character
          -1.0  segment lemma not found anywhere
          +0.5  per reduction vs max segment count (simplicity bonus)
        """
        if not segments:
            return -100.0

        score = 0.0
        max_segments = max(len(segments), 1)

        for seg in segments:
            lemma = seg.lemma

            if self._vocab.is_indeclinable(lemma):
                score += 3.0
            elif self._vocab.contains(lemma):
                score += 2.0
            else:
                score -= 1.0

            if seg.pos is not None:
                score += 1.0

            if len(seg.surface) == 1:
                score -= 2.0

        # Simplicity bonus: fewer segments is better
        # Compare against max_segments (the largest candidate we consider)
        simplicity_bonus = (max_segments - len(segments)) * 0.5
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

        def _add(segs: list[Segment]) -> None:
            key = tuple(s.surface for s in segs)
            if key not in seen and len(candidates) < _MAX_CANDIDATES:
                seen.add(key)
                candidates.append(segs)

        # 1. Original split
        if segments:
            _add(segments)

        # 2. Unsplit -- whole string as one segment
        if original_slp1:
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

        # Greedy longest-match from left
        greedy = self._greedy_split(text)
        if greedy and len(greedy) > 1:
            add_fn(greedy)

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

        return Segment(surface=surface, lemma=lemma, pos=pos)
