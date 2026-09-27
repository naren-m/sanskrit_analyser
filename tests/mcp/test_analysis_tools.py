"""Tests for the MCP analysis tools."""

from sanskrit_analyzer.mcp.tools.analysis import build_analysis_tools


async def test_build_analysis_tools() -> None:
    tools, dispatch = build_analysis_tools()
    assert {t.name for t in tools} == {
        "analyze_sentence",
        "split_sandhi",
        "get_morphology",
        "transliterate",
    }
    # The dispatcher returns None for tools it does not own, so the server can
    # try the next tool group.
    assert await dispatch("not_a_tool", {}) is None
