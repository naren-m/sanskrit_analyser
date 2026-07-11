"""Tests for the diff view component logic."""

from unittest.mock import patch

import pytest

from sanskrit_analyzer.ui.components.diff_view import (
    _compute_differences,
    _flatten_words,
    _compare_words,
    _render_parse_column,
    render_diff_view,
)


class TestRenderParseColumn:
    """Tests for _render_parse_column robustness and escaping."""

    def test_none_confidence_does_not_crash(self) -> None:
        """A None parse confidence renders as 0% instead of raising."""
        with patch("sanskrit_analyzer.ui.components.diff_view.st") as mock_st:
            _render_parse_column({"confidence": None, "sandhi_groups": []})
            rendered = mock_st.markdown.call_args[0][0]
            assert "0%" in rendered

    def test_escapes_backend_html(self) -> None:
        """HTML in backend surface/word data is escaped in the diff column."""
        parse = {
            "confidence": 0.5,
            "sandhi_groups": [
                {
                    "surface_form": "<b>x</b>",
                    "scripts": {"devanagari": "<b>x</b>"},
                    "base_words": [
                        {"lemma": "<i>w</i>", "scripts": {"devanagari": "<i>w</i>"}}
                    ],
                }
            ],
        }
        with patch("sanskrit_analyzer.ui.components.diff_view.st") as mock_st:
            _render_parse_column(parse)
            rendered = mock_st.markdown.call_args[0][0]
            assert "<b>x</b>" not in rendered
            assert "&lt;b&gt;x&lt;/b&gt;" in rendered


class TestRenderDiffViewConfidence:
    """Tests for confidence handling in the compare selectboxes."""

    def test_none_confidence_in_options_does_not_crash(self) -> None:
        """None confidence in parse options renders as 0% without raising."""
        parses = [
            {"confidence": None, "sandhi_groups": []},
            {"confidence": None, "sandhi_groups": []},
        ]
        with patch("sanskrit_analyzer.ui.components.diff_view.st") as mock_st:
            mock_st.button.return_value = False
            mock_st.columns.return_value = (mock_st, mock_st)
            mock_st.selectbox.side_effect = ["Parse 1 (0%)", "Parse 2 (0%)"]
            # Should not raise a TypeError building the options dict.
            render_diff_view(parses, on_close=lambda: None)


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
