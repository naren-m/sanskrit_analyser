"""Integration tests for MCP server."""

import pytest

from indic_transliteration import sanscript
from indic_transliteration.sanscript import transliterate
from sanskrit_analyzer.analyzer import Analyzer
from sanskrit_analyzer.data.dhatu_db import DhatuDB
from sanskrit_analyzer.mcp.server import create_server, health_check
from mcp.server import Server
from starlette.applications import Starlette
from starlette.routing import Route
from starlette.testclient import TestClient


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
    async def test_health_check_returns_expected_fields(self) -> None:
        """Test that health check returns status, version, and components."""
        app = Starlette(routes=[Route("/health", health_check)])
        client = TestClient(app)
        response = client.get("/health")

        assert response.status_code in (200, 503)
        data = response.json()
        assert "status" in data
        assert "version" in data
        assert "components" in data
        assert "dhatu_db" in data["components"]
        assert "analyzer" in data["components"]


class TestEndToEnd:
    """End-to-end tests for common workflows."""

    def test_dhatu_lookup_workflow(self) -> None:
        """Test looking up a dhatu returns list."""
        db = DhatuDB()
        results = db.search("go", limit=5)
        assert isinstance(results, list)

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
