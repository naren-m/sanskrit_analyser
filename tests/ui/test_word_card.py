"""Tests for the word card component helpers."""

from unittest.mock import MagicMock, patch

from sanskrit_analyzer.ui.components.word_card import (
    _meaning_to_str,
    _render_confidence_footer,
    _render_meanings_section,
)


class TestMeaningToStr:
    """Tests for normalizing meaning entries to display strings."""

    def test_plain_string_passthrough(self) -> None:
        """A plain string meaning is returned unchanged."""
        assert _meaning_to_str("goes") == "goes"

    def test_dict_with_text_key(self) -> None:
        """A dict meaning uses its text field."""
        assert _meaning_to_str({"text": "to go"}) == "to go"

    def test_dict_with_meaning_key(self) -> None:
        """A dict meaning falls back to the meaning field."""
        assert _meaning_to_str({"meaning": "pleasing"}) == "pleasing"

    def test_empty_dict_returns_empty(self) -> None:
        """A dict without a known key returns an empty string."""
        assert _meaning_to_str({}) == ""


class TestRenderMeaningsSection:
    """Tests for the meanings section rendering."""

    def test_renders_dict_meanings_without_crash(self) -> None:
        """Dict-shaped meanings render as strings instead of raising."""
        with patch("sanskrit_analyzer.ui.components.word_card.st") as mock_st:
            _render_meanings_section([{"text": "to go"}, "pleasing"])
            rendered = mock_st.markdown.call_args[0][0]
            assert "to go" in rendered
            assert "pleasing" in rendered

    def test_escapes_html_in_meanings(self) -> None:
        """HTML in backend meanings is escaped, not interpolated raw."""
        with patch("sanskrit_analyzer.ui.components.word_card.st") as mock_st:
            _render_meanings_section(["<script>alert(1)</script>"])
            rendered = mock_st.markdown.call_args[0][0]
            assert "<script>alert(1)</script>" not in rendered
            assert "&lt;script&gt;" in rendered


class TestRenderConfidenceFooter:
    """Tests for confidence footer robustness."""

    def test_none_confidence_does_not_crash(self) -> None:
        """A None confidence renders as 0% instead of raising TypeError."""
        with patch("sanskrit_analyzer.ui.components.word_card.st") as mock_st:
            _render_confidence_footer(None)  # type: ignore[arg-type]
            rendered = mock_st.markdown.call_args[0][0]
            assert "0%" in rendered
