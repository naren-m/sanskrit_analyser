"""Tests for the diff view component logic."""

import pytest

from sanskrit_analyzer.ui.components.diff_view import (
    _compute_differences,
    _flatten_words,
    _compare_words,
)


class TestComputeDifferences:
    """Tests for _compute_differences function."""

    def test_identical_parses(self) -> None:
        """Identical parses have no differences."""
        parse = {
            "sandhi_groups": [
                {
                    "base_words": [
                        {
                            "lemma": "rama",
                            "scripts": {"devanagari": "राम"},
                            "morphology": {"pos": "noun"},
                        }
                    ]
                }
            ]
        }
        diffs = _compute_differences(parse, parse)
        assert diffs == []

    def test_different_word_count(self) -> None:
        """Different word counts are detected."""
        left = {
            "sandhi_groups": [
                {"base_words": [{"lemma": "a"}, {"lemma": "b"}]}
            ]
        }
        right = {
            "sandhi_groups": [
                {"base_words": [{"lemma": "a"}]}
            ]
        }
        diffs = _compute_differences(left, right)
        assert any("Word count" in d for d in diffs)

    def test_different_sandhi_groups(self) -> None:
        """Different sandhi group counts are detected."""
        left = {
            "sandhi_groups": [
                {"base_words": [{"lemma": "a"}]},
                {"base_words": [{"lemma": "b"}]},
            ]
        }
        right = {
            "sandhi_groups": [
                {"base_words": [{"lemma": "a"}, {"lemma": "b"}]}
            ]
        }
        diffs = _compute_differences(left, right)
        assert any("Sandhi groups" in d for d in diffs)

    def test_different_lemmas(self) -> None:
        """Different lemmas are detected."""
        left = {
            "sandhi_groups": [
                {
                    "base_words": [
                        {"lemma": "rama", "scripts": {"devanagari": "राम"}}
                    ]
                }
            ]
        }
        right = {
            "sandhi_groups": [
                {
                    "base_words": [
                        {"lemma": "lakshmana", "scripts": {"devanagari": "लक्ष्मण"}}
                    ]
                }
            ]
        }
        diffs = _compute_differences(left, right)
        assert any("Different lemma" in d for d in diffs)


class TestFlattenWords:
    """Tests for _flatten_words function."""

    def test_empty_groups(self) -> None:
        """Empty groups return empty list."""
        assert _flatten_words([]) == []

    def test_single_group(self) -> None:
        """Single group returns its words."""
        groups = [{"base_words": [{"lemma": "a"}, {"lemma": "b"}]}]
        words = _flatten_words(groups)
        assert len(words) == 2
        assert words[0]["lemma"] == "a"

    def test_multiple_groups(self) -> None:
        """Multiple groups flatten correctly."""
        groups = [
            {"base_words": [{"lemma": "a"}]},
            {"base_words": [{"lemma": "b"}, {"lemma": "c"}]},
        ]
        words = _flatten_words(groups)
        assert len(words) == 3
        assert [w["lemma"] for w in words] == ["a", "b", "c"]


class TestCompareWords:
    """Tests for _compare_words function."""

    def test_identical_words(self) -> None:
        """Identical words return None."""
        word = {
            "lemma": "rama",
            "scripts": {"devanagari": "राम"},
            "morphology": {"pos": "noun"},
        }
        assert _compare_words(word, word, 1) is None

    def test_different_lemmas(self) -> None:
        """Different lemmas are reported."""
        left = {
            "lemma": "rama",
            "scripts": {"devanagari": "राम"},
            "morphology": {"pos": "noun"},
        }
        right = {
            "lemma": "sita",
            "scripts": {"devanagari": "सीता"},
            "morphology": {"pos": "noun"},
        }
        diff = _compare_words(left, right, 1)
        assert diff is not None
        assert "Different lemma" in diff

    def test_same_lemma_different_morphology(self) -> None:
        """Same lemma with different morphology is reported."""
        left = {
            "lemma": "rama",
            "scripts": {"devanagari": "राम"},
            "morphology": {"pos": "noun", "case": "nominative"},
        }
        right = {
            "lemma": "rama",
            "scripts": {"devanagari": "राम"},
            "morphology": {"pos": "noun", "case": "accusative"},
        }
        diff = _compare_words(left, right, 2)
        assert diff is not None
        assert "Different analysis" in diff
