"""MCP server implementation for Sanskrit Analyzer."""

import argparse
from collections.abc import Callable
from typing import Any

from mcp.server.fastmcp import FastMCP

from sanskrit_analyzer.config import Config, MCPServerConfig

# Global server instance for tool registration
_server: FastMCP | None = None


def create_server(config: MCPServerConfig | None = None) -> FastMCP:
    """Create and configure the MCP server.

    Args:
        config: MCP server configuration. Uses defaults from Config if not provided.
    """
    global _server

    if config is None:
        config = Config().mcp

    _server = FastMCP(
        name="Sanskrit Analyzer",
        instructions="Sanskrit text analysis with morphology, dhatu lookup, and grammar tools",
        host=config.host,
        port=config.port,
    )

    # Register tools
    _register_tools(_server)

    return _server


def _register_tools(server: FastMCP) -> None:
    """Register all MCP tools with the server.

    Tools are imported from their respective modules and registered directly.
    The docstrings in the tool modules serve as the MCP tool descriptions.
    """
    from sanskrit_analyzer.mcp.tools.analysis import (
        analyze_sentence,
        get_morphology,
        split_sandhi,
        transliterate,
    )
    from sanskrit_analyzer.mcp.tools.dhatu import (
        conjugate_verb,
        list_gana,
        lookup_dhatu,
        search_dhatu,
    )
    from sanskrit_analyzer.mcp.tools.grammar import (
        explain_parse,
        get_pratyaya,
        identify_compound,
        resolve_ambiguity,
    )

    # Register all tools - the @server.tool() decorator uses each function's
    # name and docstring for MCP metadata
    tools: list[Callable[..., Any]] = [
        # Analysis tools
        analyze_sentence,
        split_sandhi,
        get_morphology,
        transliterate,
        # Dhatu tools
        lookup_dhatu,
        search_dhatu,
        conjugate_verb,
        list_gana,
        # Grammar tools
        explain_parse,
        identify_compound,
        get_pratyaya,
        resolve_ambiguity,
    ]

    for tool_fn in tools:
        server.tool()(tool_fn)


def main() -> None:
    """Entry point for running the MCP server."""
    # Load config (includes env var overrides)
    app_config = Config.load(validate=False)
    mcp_config = app_config.mcp

    parser = argparse.ArgumentParser(description="Sanskrit Analyzer MCP Server")
    parser.add_argument(
        "--host",
        default=mcp_config.host,
        help=f"Host to bind to (default: {mcp_config.host})",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=mcp_config.port,
        help=f"Port to listen on (default: {mcp_config.port})",
    )
    parser.add_argument(
        "--transport",
        choices=["sse", "stdio"],
        default="sse",
        help="Transport protocol (default: sse)",
    )
    args = parser.parse_args()

    # Override config with CLI args
    mcp_config.host = args.host
    mcp_config.port = args.port

    server = create_server(config=mcp_config)
    server.run(transport=args.transport)


if __name__ == "__main__":
    main()
