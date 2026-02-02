"""Tests for FastAPI application."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient

from sanskrit_analyzer import __version__
from sanskrit_analyzer.api.app import create_app
from sanskrit_analyzer.config import Config


@pytest.fixture
def mock_analyzer() -> MagicMock:
    """Create a mock analyzer."""
    analyzer = MagicMock()
    analyzer.get_available_engines = MagicMock(return_value=["vidyut", "dharmamitra"])
    analyzer._cache = MagicMock()
    analyzer.health_check = AsyncMock(return_value={
        "engine_vidyut": True,
        "engine_dharmamitra": True,
        "engine_heritage": False,
        "cache_memory": True,
        "cache_redis": False,
        "cache_sqlite": True,
        "disambiguation_rules": True,
        "disambiguation_llm": False,
    })
    return analyzer


@pytest.fixture
def config() -> Config:
    """Create test config."""
    config = Config()
    config.engines.vidyut = False
    config.engines.dharmamitra = False
    config.engines.heritage = False
    config.cache.redis_enabled = False
    config.cache.sqlite_enabled = False
    config.disambiguation.llm_enabled = False
    return config


class TestAppCreation:
    """Tests for app factory."""

    def test_create_app_default(self) -> None:
        """Test creating app with defaults."""
        app = create_app()
        assert app.title == "Sanskrit Analyzer API"
        assert app.version == __version__

    def test_create_app_with_config(self, config: Config) -> None:
        """Test creating app with custom config."""
        app = create_app(config)
        # Config passed to factory
        assert app is not None

    def test_create_app_with_cors(self) -> None:
        """Test creating app with custom CORS origins."""
        app = create_app(cors_origins=["http://localhost:3000"])
        # CORS middleware is added
        assert any("CORSMiddleware" in str(m) for m in app.user_middleware)


class TestHealthEndpoint:
    """Tests for health check endpoints."""

    @pytest.fixture
    def client(self, config: Config, mock_analyzer: MagicMock) -> TestClient:
        """Create test client with mocked analyzer."""
        app = create_app(config)
        # Manually set state instead of relying on lifespan
        app.state.analyzer = mock_analyzer
        app.state.config = config
        return TestClient(app, raise_server_exceptions=True)

    def test_health_check(self, client: TestClient) -> None:
        """Test basic health check."""
        response = client.get("/health")
        assert response.status_code == 200

        data = response.json()
        assert data["status"] == "healthy"
        assert data["version"] == __version__
        assert isinstance(data["engines"], list)
        assert isinstance(data["cache_enabled"], bool)

    def test_detailed_health_check(self, client: TestClient) -> None:
        """Test detailed health check."""
        response = client.get("/health/detailed")
        assert response.status_code == 200

        data = response.json()
        assert data["status"] == "healthy"
        assert "engines" in data
        assert "cache" in data
        assert "disambiguation" in data

        # Check structure
        assert isinstance(data["engines"], dict)
        assert "vidyut" in data["engines"]
        assert "dharmamitra" in data["engines"]
        assert "heritage" in data["engines"]

        assert isinstance(data["cache"], dict)
        assert "memory" in data["cache"]
        assert "redis" in data["cache"]
        assert "sqlite" in data["cache"]


class TestOpenAPIDocs:
    """Tests for OpenAPI documentation."""

    @pytest.fixture
    def client(self, config: Config) -> TestClient:
        """Create test client."""
        app = create_app(config)
        return TestClient(app)

    def test_openapi_json(self, client: TestClient) -> None:
        """Test OpenAPI JSON endpoint."""
        response = client.get("/openapi.json")
        assert response.status_code == 200

        data = response.json()
        assert data["info"]["title"] == "Sanskrit Analyzer API"
        assert data["info"]["version"] == __version__
        assert "paths" in data
        assert "/health" in data["paths"]

    def test_docs_page(self, client: TestClient) -> None:
        """Test Swagger docs page."""
        response = client.get("/docs")
        assert response.status_code == 200
        assert "swagger" in response.text.lower()

    def test_redoc_page(self, client: TestClient) -> None:
        """Test ReDoc page."""
        response = client.get("/redoc")
        assert response.status_code == 200
        assert "redoc" in response.text.lower()


class TestCORSMiddleware:
    """Tests for CORS configuration."""

    def test_cors_preflight(self) -> None:
        """Test CORS preflight request."""
        app = create_app(cors_origins=["http://localhost:3000"])
        client = TestClient(app)

        response = client.options(
            "/health",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "GET",
            },
        )
        assert response.status_code == 200
        assert "access-control-allow-origin" in response.headers

    def test_cors_actual_request(self, config: Config, mock_analyzer: MagicMock) -> None:
        """Test CORS on actual request."""
        app = create_app(config, cors_origins=["http://localhost:3000"])
        app.state.analyzer = mock_analyzer
        app.state.config = config
        client = TestClient(app)

        response = client.get(
            "/health",
            headers={"Origin": "http://localhost:3000"},
        )
        assert response.status_code == 200
        assert "access-control-allow-origin" in response.headers
