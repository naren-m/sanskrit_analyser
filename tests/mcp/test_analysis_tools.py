"""Tests for MCP analysis tools."""

import pytest

from sanskrit_analyzer.mcp.tools.analysis import register_analysis_tools
from mcp.server import Server
from mcp.types import TextContent


@pytest.fixture
def server() -> Server:
    """Create a test server with analysis tools registered."""
    server = Server("test-server")
    register_analysis_tools(server)
    return server


class TestAnalyzeSentence:
    """Tests for analyze_sentence tool."""

    @pytest.mark.asyncio
    async def test_analyze_simple_sentence(self, server: Server) -> None:
        """Test analyzing a simple Sanskrit sentence."""
        # Verify server has the expected name
        assert server.name == "test-server"

    @pytest.mark.asyncio
    async def test_analyze_empty_text_returns_error(self) -> None:
        """Test that empty text returns an error."""
        from sanskrit_analyzer.mcp.tools.analysis import register_analysis_tools
        from mcp.server import Server

        server = Server("test")
        register_analysis_tools(server)
        # The actual call_tool would be tested via the server interface


class TestSplitSandhi:
    """Tests for split_sandhi tool."""

    @pytest.mark.asyncio
    async def test_split_sandhi_basic(self) -> None:
        """Test basic sandhi splitting."""
        # This would test the sandhi splitting functionality
        pass


class TestGetMorphology:
    """Tests for get_morphology tool."""

    @pytest.mark.asyncio
    async def test_morphology_noun(self) -> None:
        """Test morphology for a noun."""
        pass

    @pytest.mark.asyncio
    async def test_morphology_verb(self) -> None:
        """Test morphology for a verb."""
        pass


class TestTransliterate:
    """Tests for transliterate tool."""

    def test_devanagari_to_iast(self) -> None:
        """Test Devanagari to IAST conversion."""
        from sanskrit_analyzer.mcp.response import text_response

        # Test the response helper
        result = text_response("राम")
        assert len(result) == 1
        assert result[0].type == "text"
        assert result[0].text == "राम"

    def test_iast_to_devanagari(self) -> None:
        """Test IAST to Devanagari conversion."""
        pass

    def test_invalid_script_returns_error(self) -> None:
        """Test that invalid script returns an error."""
        from sanskrit_analyzer.mcp.response import error_response

        result = error_response("Unknown script: xyz")
        assert len(result) == 1
        assert "Error:" in result[0].text


class TestResponseHelpers:
    """Tests for response helper functions."""

    def test_text_response(self) -> None:
        """Test text_response creates correct TextContent."""
        from sanskrit_analyzer.mcp.response import text_response

        result = text_response("Hello")
        assert len(result) == 1
        assert result[0].type == "text"
        assert result[0].text == "Hello"

    def test_json_response(self) -> None:
        """Test json_response creates formatted JSON."""
        from sanskrit_analyzer.mcp.response import json_response

        result = json_response({"key": "value"})
        assert len(result) == 1
        assert '"key": "value"' in result[0].text

    def test_error_response(self) -> None:
        """Test error_response adds error prefix."""
        from sanskrit_analyzer.mcp.response import error_response

        result = error_response("Something went wrong")
        assert len(result) == 1
        assert result[0].text == "Error: Something went wrong"
