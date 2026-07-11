"""Tests for MCP grammar tools."""

import pytest

from sanskrit_analyzer.mcp.response import error_response
from sanskrit_analyzer.mcp.tools.grammar import build_grammar_tools


class TestGrammarToolsRegistration:
    """Tests for grammar tools registration."""

    def test_build_exposes_expected_tools(self) -> None:
        """build_grammar_tools returns the four grammar tool specs."""
        tools, _dispatch = build_grammar_tools()
        names = {t.name for t in tools}
        assert names == {
            "explain_parse",
            "identify_compound",
            "get_pratyaya",
            "resolve_ambiguity",
        }

    @pytest.mark.asyncio
    async def test_dispatch_returns_none_for_unknown_tool(self) -> None:
        """The dispatcher returns None for tools it does not own."""
        _tools, dispatch = build_grammar_tools()
        assert await dispatch("not_a_tool", {}) is None


class TestGrammarToolErrors:
    """Tests for grammar tool error handling."""

    def test_empty_text_error_response(self) -> None:
        """Test that empty text generates appropriate error."""
        result = error_response("text parameter is required")
        assert "text parameter is required" in result[0].text
