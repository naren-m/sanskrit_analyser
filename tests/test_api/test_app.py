"""Tests for FastAPI application."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient

from sanskrit_analyzer import __version__
from sanskrit_analyzer.api.app import _resolve_cors_origins, create_app
from sanskrit_analyzer.config import Config
from tests._cases import check_cases


@pytest.fixture
def mock_analyzer() -> MagicMock:
    """Create a mock analyzer."""
    analyzer = MagicMock()
    analyzer.get_available_engines = MagicMock(return_value=["vidyut"])
    analyzer._cache = MagicMock()
    analyzer.health_check = AsyncMock(return_value={
        "engine_vidyut": True,
        "engine_local_byt5": False,
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
    config.cache.redis_enabled = False
    config.cache.sqlite_enabled = False
    config.disambiguation.llm_enabled = False
    return config


def test_create_app_defaults() -> None:
    app = create_app()
    assert app.title == "Sanskrit Analyzer API"
    assert app.version == __version__


@pytest.fixture
def client(config: Config, mock_analyzer: MagicMock) -> TestClient:
    """Test client with a mocked analyzer (state set by hand, not by lifespan)."""
    app = create_app(config)
    app.state.analyzer = mock_analyzer
    app.state.config = config
    return TestClient(app, raise_server_exceptions=True)


def test_health_endpoints(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["version"] == __version__
    assert isinstance(data["engines"], list)
    assert isinstance(data["cache_enabled"], bool)

    response = client.get("/health/detailed")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "disambiguation" in data
    assert data["engines"] == {"vidyut": True, "local_byt5": False}
    assert isinstance(data["cache"], dict)
    assert {"memory", "redis", "sqlite"} <= set(data["cache"])


# (row id, path, substring the lowercased page must contain)
DOC_PAGE_CASES = [
    ("swagger-ui", "/docs", "swagger"),
    ("redoc", "/redoc", "redoc"),
]


def test_openapi_docs(config: Config) -> None:
    client = TestClient(create_app(config))

    response = client.get("/openapi.json")
    assert response.status_code == 200
    data = response.json()
    assert data["info"]["title"] == "Sanskrit Analyzer API"
    assert data["info"]["version"] == __version__
    assert "/health" in data["paths"]

    def check(path, needle):
        response = client.get(path)
        assert response.status_code == 200
        assert needle in response.text.lower()

    check_cases(DOC_PAGE_CASES, check)


def _cors(app):
    return next(m for m in app.user_middleware if "CORSMiddleware" in str(m))


def test_cors(config: Config, mock_analyzer: MagicMock) -> None:
    origin = "http://localhost:3000"
    app = create_app(config, cors_origins=[origin])
    app.state.analyzer = mock_analyzer
    app.state.config = config
    client = TestClient(app)

    # Preflight and an actual request both carry the allow-origin header.
    response = client.options(
        "/health",
        headers={"Origin": origin, "Access-Control-Request-Method": "GET"},
    )
    assert response.status_code == 200
    assert "access-control-allow-origin" in response.headers
    response = client.get("/health", headers={"Origin": origin})
    assert response.status_code == 200
    assert "access-control-allow-origin" in response.headers

    # Explicit origins enable credentialed CORS; a wildcard origin must not be
    # combined with credentials.
    assert _cors(app).kwargs["allow_credentials"] is True
    assert _cors(create_app(cors_origins=["*"])).kwargs["allow_credentials"] is False


def test_default_cors_origins(monkeypatch: pytest.MonkeyPatch) -> None:
    # SANSKRIT_CORS_ORIGINS drives the default allowlist.
    monkeypatch.setenv("SANSKRIT_CORS_ORIGINS", "https://a.example, https://b.example")
    assert _resolve_cors_origins() == ["https://a.example", "https://b.example"]

    # Without the env var, default origins are localhost dev hosts.
    monkeypatch.delenv("SANSKRIT_CORS_ORIGINS")
    origins = _resolve_cors_origins()
    assert "*" not in origins
    assert all(o.startswith("http://") for o in origins)
