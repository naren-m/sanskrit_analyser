"""Tests for SplitValidator: candidate generation, scoring, and validation."""

from sanskrit_analyzer.engines.base import Segment
from sanskrit_analyzer.validation.split_validator import SplitValidator
from sanskrit_analyzer.validation.vocabulary import Vocabulary
from tests._cases import check_cases

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _seg(surface: str, lemma: str | None = None, pos: str | None = None) -> Segment:
    """Create a Segment with sensible defaults for testing."""
    return Segment(
        surface=surface,
        lemma=lemma or surface,
        pos=pos,
    )


def _vocab_with(*slp1_words: str, indeclinables: set[str] | None = None) -> Vocabulary:
    """Build a tiny Vocabulary from a list of SLP1 lemmas."""
    words: dict[str, dict] = {}
    indec = indeclinables or set()
    for w in slp1_words:
        words[w] = {
            "slp1": w,
            "lemma": w,
            "type": "indeclinable" if w in indec else "noun",
            "indeclinable": w in indec,
        }
    return Vocabulary(words=words, indeclinables=indec)


class _FakeGuard:
    """Stand-in for KoshaVocabulary over a fixed word set.

    Like the real kosha it also accepts short fragments (``uSA``, ``asanam``)
    as genuine entries; that permissiveness is what makes the merge case fail.
    """

    def __init__(self, words: set[str]) -> None:
        self._words = words

    def contains(self, surface: str) -> bool:
        return surface in self._words


DEFAULT = Vocabulary.load_default()


def _surfaces(segments) -> list[str]:
    return [s.surface for s in segments]


def _no_single_chars(result) -> None:
    single_chars = [s for s in _surfaces(result) if len(s) == 1]
    assert not single_chars, f"Got single-char segments: {single_chars}"


def _is(*surfaces: str):
    def check(result) -> None:
        assert _surfaces(result) == list(surfaces)

    return check


def _lemma(lemma: str):
    def check(result) -> None:
        assert len(result) == 1
        assert result[0].lemma == lemma

    return check


def _nonempty(result) -> None:
    assert len(result) >= 1


# ---------------------------------------------------------------------------
# validate_and_rescore
# ---------------------------------------------------------------------------

# (id, vocabulary, word guard, input segments, original SLP1, check on result)
VALIDATE_CASES = [
    # Indeclinables must never be split; vidyut might produce ["a", "Ta"].
    ("avyaya-aTa-stays-unsplit", DEFAULT, None, [_seg("a"), _seg("Ta")], "aTa", _lemma("aTa")),
    ("avyaya-iti-stays-unsplit", DEFAULT, None, [_seg("i"), _seg("ti")], "iti", _lemma("iti")),
    ("avyaya-single-segment-passthrough", DEFAULT, None,
     [_seg("aTa", lemma="aTa")], "aTa", _lemma("aTa")),
    # Simulated vidyut bad split ["y", "o", "gasUtra"]: the validator finds a
    # better candidate with no single-character junk.
    ("yogasutra-no-single-char-junk", _vocab_with("yoga", "sUtra"), None,
     [_seg("y"), _seg("o"), _seg("gasUtra")], "yogasUtra", _no_single_chars),
    ("single-valid-word-stays", _vocab_with("yoga"), None,
     [_seg("yoga", lemma="yoga")], "yoga", _lemma("yoga")),
    # Long input that could generate many candidates: the count is capped and
    # validation does not explode.
    ("long-input-candidate-count-capped", _vocab_with("yoga", "sUtra"), None,
     [_seg("yogasUtrapariRAma")], "yogasUtrapariRAma", _nonempty),
    # With empty vocab all lemmas are unknown (-1.0 each); the unsplit
    # candidate has fewer penalties plus the simplicity bonus. Without vocab
    # knowledge the validator prefers the conservative unsplit form.
    ("empty-vocab-passes-through", Vocabulary(), None,
     [_seg("yoga", lemma="yoga"), _seg("sUtra", lemma="sUtra")], "yogasUtra", _nonempty),
    ("empty-segments-returns-empty", Vocabulary(), None, [], "", _is()),
    ("empty-vocab-single-word", Vocabulary(), None, [_seg("yoga")], "yoga", _is("yoga")),
    # The kosha veto must protect whole words without freezing over-splits.
    # ``_generate_candidates`` may merge fragments and split non-words, but
    # never breaks a token the kosha recognises. Absorbing a locked token into
    # a longer real word is a merge, not a break: anuSAsanam must win even
    # though uSA/asanam are locked fragments, or the veto entrenches exactly
    # the cheda over-split it was meant to guard against.
    ("guard-merge-into-longer-real-word-is-not-a-break", _vocab_with("anuSAsana"),
     _FakeGuard({"uSA", "asanam", "anuSAsanam"}),
     [_seg("an", "aYji", "subanta"), _seg("uSA", "vaS", "subanta"),
      _seg("asanam", "asana", "subanta")],
     "anuSAsanam", _is("anuSAsanam")),
    # The multi-word guard must not disable merging inside a single word.
    ("single-word-input-still-merges", _vocab_with("vana"), None,
     [_seg("van", "av", "subanta"), _seg("am", "a", "subanta")], "vanam", _is("vanam")),
]


def test_validate_and_rescore() -> None:
    def check(vocab, guard, segments, original, expect):
        sv = SplitValidator(vocabulary=vocab, word_guard=guard)
        expect(sv.validate_and_rescore(segments, original_slp1=original))

    check_cases(VALIDATE_CASES, check)


# ---------------------------------------------------------------------------
# score_candidate
# ---------------------------------------------------------------------------

# (id, vocabulary, higher-scoring candidate, lower-scoring candidate)
SCORE_CASES = [
    ("vocab-match-beats-unknown", _vocab_with("yoga", "sUtra"),
     [_seg("yoga", lemma="yoga", pos="noun"), _seg("sUtra", lemma="sUtra", pos="noun")],
     [_seg("xyz", lemma="xyz"), _seg("abc", lemma="abc")]),
    ("single-chars-penalized", _vocab_with("yoga", "sUtra"),
     [_seg("yoga", lemma="yoga")], [_seg("y"), _seg("o"), _seg("g"), _seg("a")]),
    # Indeclinable gets +3.0 + 1.0 (pos) = 4.0 base; regular +2.0 + 1.0 = 3.0.
    ("avyaya-bonus-beats-regular-word", _vocab_with("aTa", "yoga", indeclinables={"aTa"}),
     [_seg("aTa", lemma="aTa", pos="indeclinable")], [_seg("yoga", lemma="yoga", pos="noun")]),
    ("fewer-segments-simplicity-bonus", Vocabulary(),
     [_seg("ab", lemma="ab"), _seg("cd", lemma="cd")],
     [_seg("a"), _seg("b"), _seg("c"), _seg("d")]),
    ("pos-morphology-bonus", Vocabulary(),
     [_seg("test", lemma="test", pos="noun")], [_seg("test", lemma="test")]),
]


def test_score_candidate_ordering() -> None:
    def check(vocab, better, worse):
        sv = SplitValidator(vocabulary=vocab)
        assert sv.score_candidate(better) > sv.score_candidate(worse)

    check_cases(SCORE_CASES, check)


# ---------------------------------------------------------------------------
# _generate_candidates invariants
# ---------------------------------------------------------------------------

def _keeps_locked_gaccati(candidate) -> None:
    surfaces = _surfaces(candidate)
    assert any("gacCati" in s for s in surfaces), (
        f"candidate {surfaces} broke the locked word gacCati"
    )


def _not_welded(candidate) -> None:
    for seg in candidate:
        assert " " not in seg.surface.strip(), (
            f"candidate {_surfaces(candidate)} welded across a space"
        )
        assert seg.surface != "dadarSagiriM", (
            f"candidate {_surfaces(candidate)} merged two words"
        )


# (id, vocabulary, word guard, input segments, original SLP1, invariant every
# generated candidate must hold)
CANDIDATE_CASES = [
    # The veto's real job is preserved: a locked word is never broken up.
    ("guard-locked-token-never-split-apart", _vocab_with("gam"), _FakeGuard({"gacCati"}),
     [_seg("gacCati", "gam", "tinanta")], "gacCati", _keeps_locked_gaccati),
    # ``Segment`` carries no offsets, so adjacent segments that straddle a space
    # look identical to ones inside a word. Merging them welded words together
    # ("dadarSa giriSfNga..." -> "dadarSagiriSfNgasTAnpaY" | "ca"). Only shows
    # up on real multi-word lines, which single-word rows miss.
    ("merge-never-spans-a-space", _vocab_with("dadarSa", "giri"), None,
     [_seg("dadarSa", "dfS", "tinanta"), _seg("giriM", "giri", "subanta")],
     "dadarSa giriM", _not_welded),
]


def test_every_candidate_holds_invariant() -> None:
    def check(vocab, guard, segments, original, invariant):
        sv = SplitValidator(vocabulary=vocab, word_guard=guard)
        for candidate in sv._generate_candidates(segments, original_slp1=original):
            invariant(candidate)

    check_cases(CANDIDATE_CASES, check)
