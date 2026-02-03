"""MCP (Model Context Protocol) server for Sanskrit Analyzer.

This module exposes the Sanskrit Analyzer as an MCP server, enabling AI assistants
to analyze Sanskrit text, look up dhatus, and access grammar resources.
"""

from sanskrit_analyzer.mcp.server import create_server, main

__all__ = ["create_server", "main"]
