"""MCP server implementation for Sanskrit Analyzer."""

import argparse
import json
import os
import time
from dataclasses import dataclass
from typing import Any

from mcp.server import Server
from mcp.server.sse import SseServerTransport
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route

from sanskrit_analyzer.mcp.tools.analysis import register_analysis_tools
from sanskrit_analyzer.mcp.tools.dhatu import register_dhatu_tools
from sanskrit_analyzer.mcp.tools.grammar import register_grammar_tools
from sanskrit_analyzer.mcp.resources.dhatus import register_dhatu_resources
from sanskrit_analyzer.mcp.resources.grammar import register_grammar_resources

# Server start time for uptime calculation
_start_time: float = 0.0
_VERSION = "0.1.0"


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


async def health_check(request: Request) -> JSONResponse:
    """Health check endpoint for monitoring.

    Returns:
        JSON response with server health status.
    """
    from sanskrit_analyzer.data.dhatu_db import DhatuDB

    # Check component health
    components: dict[str, dict[str, Any]] = {}

    # Check DhatuDB
    try:
        db = DhatuDB()
        # Quick test query
        _ = db.get_by_gana(1, limit=1)
        components["dhatu_db"] = {"status": "healthy"}
    except Exception as e:
        components["dhatu_db"] = {"status": "unhealthy", "error": str(e)}

    # Check Analyzer
    try:
        from sanskrit_analyzer import Analyzer
        from sanskrit_analyzer.config import Config

        _ = Analyzer(Config())
        components["analyzer"] = {"status": "healthy"}
    except Exception as e:
        components["analyzer"] = {"status": "unhealthy", "error": str(e)}

    # Determine overall status
    all_healthy = all(c["status"] == "healthy" for c in components.values())
    status = "healthy" if all_healthy else "degraded"
    status_code = 200 if all_healthy else 503

    # Calculate uptime
    uptime_seconds = time.time() - _start_time if _start_time > 0 else 0

    return JSONResponse(
        {
            "status": status,
            "version": _VERSION,
            "uptime_seconds": round(uptime_seconds, 2),
            "components": components,
        },
        status_code=status_code,
    )


def create_app(config: MCPServerConfig | None = None) -> Starlette:
    """Create the Starlette application with SSE transport.

    Args:
        config: Server configuration. Uses defaults if not provided.

    Returns:
        Starlette application instance.
    """
    global _start_time
    _start_time = time.time()

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
            Route("/health", endpoint=health_check, methods=["GET"]),
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
