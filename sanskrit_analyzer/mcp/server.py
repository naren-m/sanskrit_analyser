"""MCP server implementation for Sanskrit Analyzer."""

import argparse
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
    """Register all MCP tools with the server."""
    from sanskrit_analyzer.mcp.tools.analysis import analyze_sentence as _analyze

    @server.tool()
    async def analyze_sentence(
        text: str,
        mode: str | None = None,
        verbosity: str | None = None,
    ) -> dict[str, Any]:
        """Analyze a Sanskrit sentence and return full morphological breakdown.

        Args:
            text: Sanskrit text to analyze (Devanagari, IAST, or SLP1).
            mode: Analysis mode - 'educational', 'production', or 'academic'.
            verbosity: Response detail level - 'minimal', 'standard', or 'detailed'.

        Returns:
            Analysis result with sandhi_groups, words, morphology, and confidence.
        """
        return await _analyze(text, mode, verbosity)


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
