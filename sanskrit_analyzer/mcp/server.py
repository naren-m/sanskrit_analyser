"""MCP server implementation for Sanskrit Analyzer."""

import argparse

from mcp.server.fastmcp import FastMCP

from sanskrit_analyzer.config import Config, MCPServerConfig


def create_server(config: MCPServerConfig | None = None) -> FastMCP:
    """Create and configure the MCP server.

    Args:
        config: MCP server configuration. Uses defaults from Config if not provided.
    """
    if config is None:
        config = Config().mcp

    return FastMCP(
        name="Sanskrit Analyzer",
        instructions="Sanskrit text analysis with morphology, dhatu lookup, and grammar tools",
        host=config.host,
        port=config.port,
    )


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
