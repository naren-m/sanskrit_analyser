"""Tests for MCP analysis tools and response helpers."""

import pytest

from sanskrit_analyzer.mcp.response import error_response, json_response, text_response
from sanskrit_analyzer.mcp.tools.analysis import build_analysis_tools


class TestAnalyzeSentence:
    """Tests for analyze_sentence tool."""

    def test_build_exposes_expected_tools(self) -> None:
        """build_analysis_tools returns the four analysis tool specs."""
        tools, _dispatch = build_analysis_tools()
        names = {t.name for t in tools}
        assert names == {
            "analyze_sentence",
            "split_sandhi",
            "get_morphology",
            "transliterate",
        }

    @pytest.mark.asyncio
    async def test_dispatch_returns_none_for_unknown_tool(self) -> None:
        """The dispatcher returns None for tools it does not own."""
        _tools, dispatch = build_analysis_tools()
        assert await dispatch("not_a_tool", {}) is None


class TestResponseHelpers:
    """Tests for response helper functions."""

    def test_text_response_creates_text_content(self) -> None:
        """Test text_response creates correct TextContent."""
        result = text_response("Hello")
        assert len(result) == 1
        assert result[0].type == "text"
        assert result[0].text == "Hello"

    def test_json_response_creates_formatted_json(self) -> None:
        """Test json_response creates formatted JSON."""
        result = json_response({"key": "value"})
        assert len(result) == 1
        assert '"key": "value"' in result[0].text

    def test_error_response_adds_error_prefix(self) -> None:
        """Test error_response adds error prefix."""
        result = error_response("Something went wrong")
        assert len(result) == 1
        assert result[0].text == "Error: Something went wrong"
