"""MCP server implementation for Sanskrit Analyzer."""

import argparse
import os

from mcp.server.fastmcp import FastMCP

# Default configuration
DEFAULT_HOST = "0.0.0.0"
DEFAULT_PORT = 8001


def create_server(host: str = DEFAULT_HOST, port: int = DEFAULT_PORT) -> FastMCP:
    """Create and configure the MCP server.

    Args:
        host: Host to bind to.
        port: Port to listen on.

    Returns:
        Configured FastMCP server instance.
    """
    mcp = FastMCP(
        name="Sanskrit Analyzer",
        instructions="Sanskrit text analysis with morphology, dhatu lookup, and grammar tools",
        host=host,
        port=port,
    )
    return mcp


def main() -> None:
    """Entry point for running the MCP server."""
    parser = argparse.ArgumentParser(description="Sanskrit Analyzer MCP Server")
    parser.add_argument(
        "--host",
        default=os.environ.get("MCP_HOST", DEFAULT_HOST),
        help=f"Host to bind to (default: {DEFAULT_HOST})",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=int(os.environ.get("MCP_PORT", str(DEFAULT_PORT))),
        help=f"Port to listen on (default: {DEFAULT_PORT})",
    )
    parser.add_argument(
        "--transport",
        choices=["sse", "stdio"],
        default="sse",
        help="Transport protocol (default: sse)",
    )
    args = parser.parse_args()

    mcp = create_server(host=args.host, port=args.port)
    mcp.run(transport=args.transport)


if __name__ == "__main__":
    main()
