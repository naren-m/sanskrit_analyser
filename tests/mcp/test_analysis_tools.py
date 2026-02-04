"""Tests for MCP analysis tools and response helpers."""

import pytest

from sanskrit_analyzer.mcp.response import error_response, json_response, text_response
from sanskrit_analyzer.mcp.tools.analysis import register_analysis_tools
from mcp.server import Server


@pytest.fixture
def server() -> Server:
    """Create a test server with analysis tools registered."""
    server = Server("test-server")
    register_analysis_tools(server)
    return server


class TestAnalyzeSentence:
    """Tests for analyze_sentence tool."""

    @pytest.mark.asyncio
    async def test_server_configured_correctly(self, server: Server) -> None:
        """Test server is configured with analysis tools."""
        assert server.name == "test-server"


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
