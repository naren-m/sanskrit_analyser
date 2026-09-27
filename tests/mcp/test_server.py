"""Tests for the MCP server (sanskrit_analyzer.mcp.server)."""

from mcp.server import Server
from starlette.testclient import TestClient

from sanskrit_analyzer.mcp.server import create_app, create_server


def test_create_server() -> None:
    server = create_server()
    assert isinstance(server, Server)
    # The name MCP clients see in their server list.
    assert server.name == "sanskrit-analyzer"


def test_app_routes_health_and_client_messages() -> None:
    """The real app serves /health and routes client POSTs to /messages/.

    /messages/ was once never mounted, so every MCP client's initialize
    POST got a 404 and no tool could be called over SSE.
    """
    client = TestClient(create_app())
    # No session_id: the SSE transport answers 400, a missing route 404.
    assert client.post("/messages/").status_code == 400
    response = client.get("/health")

    assert response.status_code in (200, 503)
    data = response.json()
    assert "status" in data
    assert "version" in data
    assert "dhatupatha" in data["components"]
    assert "analyzer" in data["components"]
