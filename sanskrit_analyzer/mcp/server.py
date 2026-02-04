"""MCP server implementation for Sanskrit Analyzer."""

import argparse
import asyncio
import os
from dataclasses import dataclass
from typing import Any

from mcp.server import Server
from mcp.server.sse import SseServerTransport
from starlette.applications import Starlette
from starlette.routing import Route

from sanskrit_analyzer.mcp.tools.analysis import register_analysis_tools
from sanskrit_analyzer.mcp.tools.dhatu import register_dhatu_tools
from sanskrit_analyzer.mcp.tools.grammar import register_grammar_tools
from sanskrit_analyzer.mcp.resources.dhatus import register_dhatu_resources
from sanskrit_analyzer.mcp.resources.grammar import register_grammar_resources


@dataclass
class MCPServerConfig:
    """Configuration for the MCP server."""

    host: str = "0.0.0.0"
    port: int = 8001
    log_level: str = "INFO"

    @classmethod
    def from_env(cls) -> "MCPServerConfig":
        """Create config from environment variables."""
        return cls(
            host=os.getenv("MCP_HOST", "0.0.0.0"),
            port=int(os.getenv("MCP_PORT", "8001")),
            log_level=os.getenv("MCP_LOG_LEVEL", "INFO"),
        )


def create_server() -> Server:
    """Create and configure the MCP server instance.

    Returns:
        Configured MCP Server instance.
    """
    server = Server("sanskrit-analyzer")

    # Register tools
    register_analysis_tools(server)
    register_dhatu_tools(server)
    register_grammar_tools(server)

    # Register resources
    register_dhatu_resources(server)
    register_grammar_resources(server)

    return server


def create_app(config: MCPServerConfig | None = None) -> Starlette:
    """Create the Starlette application with SSE transport.

    Args:
        config: Server configuration. Uses defaults if not provided.

    Returns:
        Starlette application instance.
    """
    if config is None:
        config = MCPServerConfig.from_env()

    server = create_server()
    sse = SseServerTransport("/messages/")

    async def handle_sse(request: Any) -> None:
        async with sse.connect_sse(
            request.scope, request.receive, request._send
        ) as streams:
            await server.run(
                streams[0], streams[1], server.create_initialization_options()
            )

    return Starlette(
        routes=[
            Route("/sse", endpoint=handle_sse),
        ],
    )


def main() -> None:
    """Main entry point for the MCP server."""
    parser = argparse.ArgumentParser(description="Sanskrit Analyzer MCP Server")
    parser.add_argument("--host", default=None, help="Host to bind to")
    parser.add_argument("--port", type=int, default=None, help="Port to bind to")
    parser.add_argument("--log-level", default=None, help="Log level")
    args = parser.parse_args()

    # Build config from env, then override with CLI args
    config = MCPServerConfig.from_env()
    if args.host:
        config.host = args.host
    if args.port:
        config.port = args.port
    if args.log_level:
        config.log_level = args.log_level

    import uvicorn

    uvicorn.run(
        create_app(config),
        host=config.host,
        port=config.port,
        log_level=config.log_level.lower(),
    )


if __name__ == "__main__":
    main()
