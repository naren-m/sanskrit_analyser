"""Integration tests for MCP server."""

import pytest
from indic_transliteration import sanscript
from indic_transliteration.sanscript import transliterate
from mcp.server import Server
from starlette.testclient import TestClient

from sanskrit_analyzer.analyzer import Analyzer
from sanskrit_analyzer.dhatu.dhatupatha import get_dhatu_kosha
from sanskrit_analyzer.mcp.server import create_app, create_server


class TestServerCreation:
    """Tests for MCP server creation and initialization."""

    def test_create_server_returns_configured_server(self) -> None:
        """Test that create_server returns a properly configured Server."""
        server = create_server()
        assert isinstance(server, Server)
        assert server.name == "sanskrit-analyzer"


class TestHealthCheck:
    """Tests for health check endpoint."""

    @pytest.mark.asyncio
    async def test_app_routes_health_and_client_messages(self) -> None:
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
        assert "components" in data
        assert "dhatupatha" in data["components"]
        assert "analyzer" in data["components"]


class TestEndToEnd:
    """End-to-end tests for common workflows."""

    def test_dhatu_lookup_workflow(self) -> None:
        """Looking up a root reaches the real Dhatupatha."""
        entries = get_dhatu_kosha().find("gam")
        assert [e["code"] for e in entries] == ["01.1137"]

    @pytest.mark.asyncio
    async def test_analysis_workflow(self) -> None:
        """Test analyzing Sanskrit text returns result."""
        analyzer = Analyzer()
        result = await analyzer.analyze("rama")
        assert result is not None

    def test_transliteration_workflow(self) -> None:
        """Test transliteration between scripts."""
        result = transliterate("rāma", sanscript.IAST, sanscript.DEVANAGARI)
        assert result == "राम"

        result = transliterate("राम", sanscript.DEVANAGARI, sanscript.IAST)
        assert result == "rāma"
