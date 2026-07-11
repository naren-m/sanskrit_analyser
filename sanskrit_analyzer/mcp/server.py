"""MCP server implementation for Sanskrit Analyzer."""

import argparse
import json
import os
import time
from dataclasses import dataclass
from typing import Any

from mcp.server import Server
from mcp.server.sse import SseServerTransport
from mcp.types import Resource, TextContent, Tool
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route

from sanskrit_analyzer.mcp.response import error_response
from sanskrit_analyzer.mcp.tools.analysis import build_analysis_tools
from sanskrit_analyzer.mcp.tools.dhatu import build_dhatu_tools
from sanskrit_analyzer.mcp.tools.grammar import build_grammar_tools
from sanskrit_analyzer.mcp.resources.dhatus import build_dhatu_resources
from sanskrit_analyzer.mcp.resources.grammar import build_grammar_resources

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

    # The MCP low-level Server stores exactly one handler per request type, so
    # every tool/resource group must be aggregated into a single handler.
    # Registering each group's own @server.list_tools()/@server.call_tool()
    # (etc.) would silently overwrite all but the last group.
    tool_specs: list[Tool] = []
    tool_dispatchers = []
    for build in (build_analysis_tools, build_dhatu_tools, build_grammar_tools):
        specs, dispatch = build()
        tool_specs.extend(specs)
        tool_dispatchers.append(dispatch)

    resource_specs: list[Resource] = []
    resource_readers = []
    for build in (build_dhatu_resources, build_grammar_resources):
        specs, reader = build()
        resource_specs.extend(specs)
        resource_readers.append(reader)

    @server.list_tools()
    async def list_tools() -> list[Tool]:
        return tool_specs

    @server.call_tool()
    async def call_tool(name: str, arguments: dict) -> list[TextContent]:
        for dispatch in tool_dispatchers:
            result = await dispatch(name, arguments)
            if result is not None:
                return result
        return error_response(f"Unknown tool: {name}")

    @server.list_resources()
    async def list_resources() -> list[Resource]:
        return resource_specs

    @server.read_resource()
    async def read_resource(uri: str) -> str:
        for reader in resource_readers:
            result = await reader(str(uri))
            if result is not None:
                return result
        return json.dumps({"error": f"Unknown resource: {uri}"})

    return server


# Health-probe objects are cached so a monitoring poll doesn't rebuild a DhatuDB
# and Analyzer (an expensive load) on every request.
_health_db: Any = None
_health_analyzer: Any = None


def _get_health_probes() -> tuple[Any, Any]:
    """Lazily build and cache the DhatuDB/Analyzer used by the health check."""
    global _health_db, _health_analyzer
    if _health_db is None:
        from sanskrit_analyzer.data.dhatu_db import DhatuDB

        _health_db = DhatuDB()
    if _health_analyzer is None:
        from sanskrit_analyzer import Analyzer
        from sanskrit_analyzer.config import Config

        _health_analyzer = Analyzer(Config())
    return _health_db, _health_analyzer


async def health_check(request: Request) -> JSONResponse:
    """Health check endpoint for monitoring.

    Returns:
        JSON response with server health status.
    """
    # Check component health
    components: dict[str, dict[str, Any]] = {}

    # Check DhatuDB
    try:
        db, _ = _get_health_probes()
        # Quick test query
        _ = db.get_by_gana(1, limit=1)
        components["dhatu_db"] = {"status": "healthy"}
    except Exception as e:
        components["dhatu_db"] = {"status": "unhealthy", "error": str(e)}

    # Check Analyzer
    try:
        _get_health_probes()
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
