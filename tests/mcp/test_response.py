"""Tests for the MCP response helpers (moved out of test_analysis_tools.py)."""

from sanskrit_analyzer.mcp.response import error_response, json_response, text_response


def test_response_helpers() -> None:
    result = text_response("Hello")
    assert len(result) == 1
    assert result[0].type == "text"
    assert result[0].text == "Hello"

    result = json_response({"key": "value"})
    assert len(result) == 1
    assert '"key": "value"' in result[0].text

    result = error_response("Something went wrong")
    assert len(result) == 1
    assert result[0].text == "Error: Something went wrong"
