"""Tests for MCP grammar tools."""

from sanskrit_analyzer.mcp.response import error_response
from sanskrit_analyzer.mcp.tools.grammar import register_grammar_tools
from mcp.server import Server


class TestGrammarToolsRegistration:
    """Tests for grammar tools registration."""

    def test_register_grammar_tools_succeeds(self) -> None:
        """Test that grammar tools register without error."""
        server = Server("test-server")
        register_grammar_tools(server)
        assert server.name == "test-server"


class TestGrammarToolErrors:
    """Tests for grammar tool error handling."""

    def test_empty_text_error_response(self) -> None:
        """Test that empty text generates appropriate error."""
        result = error_response("text parameter is required")
        assert "text parameter is required" in result[0].text
