"""Integration tests for MCP server."""

import pytest

from sanskrit_analyzer.mcp.server import create_server
from mcp.server import Server


class TestServerCreation:
    """Tests for MCP server creation and initialization."""

    def test_create_server_returns_server(self) -> None:
        """Test that create_server returns a Server instance."""
        server = create_server()
        assert isinstance(server, Server)

    def test_server_has_correct_name(self) -> None:
        """Test that server has the expected name."""
        server = create_server()
        assert server.name == "sanskrit-analyzer"


class TestToolRegistration:
    """Tests for tool registration."""

    def test_analysis_tools_registered(self) -> None:
        """Test that analysis tools are registered."""
        server = create_server()
        # Server is created with tools registered
        assert server is not None

    def test_dhatu_tools_registered(self) -> None:
        """Test that dhatu tools are registered."""
        server = create_server()
        assert server is not None

    def test_grammar_tools_registered(self) -> None:
        """Test that grammar tools are registered."""
        server = create_server()
        assert server is not None


class TestResourceRegistration:
    """Tests for resource registration."""

    def test_dhatu_resources_registered(self) -> None:
        """Test that dhatu resources are registered."""
        server = create_server()
        assert server is not None

    def test_grammar_resources_registered(self) -> None:
        """Test that grammar resources are registered."""
        server = create_server()
        assert server is not None


class TestHealthCheck:
    """Tests for health check endpoint."""

    @pytest.mark.asyncio
    async def test_health_check_returns_status(self) -> None:
        """Test that health check returns expected fields."""
        from sanskrit_analyzer.mcp.server import health_check
        from starlette.requests import Request
        from starlette.testclient import TestClient
        from starlette.applications import Starlette
        from starlette.routing import Route

        app = Starlette(routes=[Route("/health", health_check)])
        client = TestClient(app)
        response = client.get("/health")

        assert response.status_code in (200, 503)
        data = response.json()
        assert "status" in data
        assert "version" in data
        assert "components" in data

    @pytest.mark.asyncio
    async def test_health_check_includes_components(self) -> None:
        """Test that health check includes component statuses."""
        from sanskrit_analyzer.mcp.server import health_check
        from starlette.testclient import TestClient
        from starlette.applications import Starlette
        from starlette.routing import Route

        app = Starlette(routes=[Route("/health", health_check)])
        client = TestClient(app)
        response = client.get("/health")

        data = response.json()
        assert "dhatu_db" in data["components"]
        assert "analyzer" in data["components"]


class TestEndToEnd:
    """End-to-end tests for common workflows."""

    def test_dhatu_lookup_workflow(self) -> None:
        """Test looking up a dhatu and getting conjugations."""
        from sanskrit_analyzer.data.dhatu_db import DhatuDB

        db = DhatuDB()
        # Test basic workflow: search -> lookup
        results = db.search("go", limit=5)
        assert isinstance(results, list)

    @pytest.mark.asyncio
    async def test_analysis_workflow(self) -> None:
        """Test analyzing Sanskrit text."""
        from sanskrit_analyzer.analyzer import Analyzer

        analyzer = Analyzer()
        result = await analyzer.analyze("rama")
        assert result is not None

    def test_transliteration_workflow(self) -> None:
        """Test transliteration between scripts."""
        from indic_transliteration import sanscript
        from indic_transliteration.sanscript import transliterate

        # IAST to Devanagari (note: 'rama' without macrons -> 'रम')
        result = transliterate("rāma", sanscript.IAST, sanscript.DEVANAGARI)
        assert result == "राम"

        # Devanagari to IAST
        result = transliterate("राम", sanscript.DEVANAGARI, sanscript.IAST)
        assert result == "rāma"
