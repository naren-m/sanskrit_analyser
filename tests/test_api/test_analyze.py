"""Tests for analyze API endpoints."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient

from sanskrit_analyzer.api.app import create_app
from sanskrit_analyzer.config import Config
from sanskrit_analyzer.models.scripts import Script, ScriptVariants
from sanskrit_analyzer.models.tree import (
    AnalysisTree,
    BaseWord,
    ConfidenceMetrics,
    ParseTree,
    SandhiGroup,
)


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


@pytest.fixture
def mock_tree() -> AnalysisTree:
    """Create a mock analysis tree."""
    scripts = ScriptVariants.from_text("rAmaH gacCati", Script.SLP1)
    return AnalysisTree(
        sentence_id="test-123",
        original_text="रामः गच्छति",
        normalized_slp1="rAmaH gacCati",
        scripts=scripts,
        parse_forest=[
            ParseTree(
                parse_id="p1",
                confidence=0.92,
                sandhi_groups=[
                    SandhiGroup(
                        surface_form="rAmaH",
                        scripts=ScriptVariants.from_text("rAmaH", Script.SLP1),
                        base_words=[
                            BaseWord(
                                lemma="rAma",
                                surface_form="rAmaH",
                                scripts=ScriptVariants.from_text("rAmaH", Script.SLP1),
                                confidence=0.95,
                            ),
                        ],
                    ),
                    SandhiGroup(
                        surface_form="gacCati",
                        scripts=ScriptVariants.from_text("gacCati", Script.SLP1),
                        base_words=[
                            BaseWord(
                                lemma="gam",
                                surface_form="gacCati",
                                scripts=ScriptVariants.from_text("gacCati", Script.SLP1),
                                confidence=0.90,
                            ),
                        ],
                    ),
                ],
            ),
        ],
        confidence=ConfidenceMetrics(overall=0.92, engine_agreement=0.90),
    )


@pytest.fixture
def mock_analyzer(mock_tree: AnalysisTree) -> MagicMock:
    """Create mock analyzer."""
    analyzer = MagicMock()
    analyzer.analyze = AsyncMock(return_value=mock_tree)
    analyzer._cache = None
    return analyzer


@pytest.fixture
def client(config: Config, mock_analyzer: MagicMock) -> TestClient:
    """Create test client."""
    app = create_app(config)
    app.state.analyzer = mock_analyzer
    app.state.config = config
    return TestClient(app)


class TestAnalyzeEndpoint:
    """Tests for POST /api/v1/analyze."""

    def test_analyze_basic(self, client: TestClient) -> None:
        """Test basic analysis."""
        response = client.post(
            "/api/v1/analyze",
            json={"text": "रामः गच्छति"},
        )
        assert response.status_code == 200

        data = response.json()
        assert data["sentence_id"] == "test-123"
        assert data["original_text"] == "रामः गच्छति"
        assert data["normalized_slp1"] == "rAmaH gacCati"
        assert len(data["parse_forest"]) == 1

    def test_analyze_with_mode(self, client: TestClient, mock_analyzer: MagicMock) -> None:
        """Test analysis with specific mode."""
        response = client.post(
            "/api/v1/analyze",
            json={"text": "test", "mode": "educational"},
        )
        assert response.status_code == 200

        # Check mode was passed
        call_kwargs = mock_analyzer.analyze.call_args[1]
        assert str(call_kwargs["mode"].value) == "educational"

    def test_analyze_with_all_parses(self, client: TestClient, mock_analyzer: MagicMock) -> None:
        """Test analysis with all parses."""
        response = client.post(
            "/api/v1/analyze",
            json={"text": "test", "return_all_parses": True},
        )
        assert response.status_code == 200

        call_kwargs = mock_analyzer.analyze.call_args[1]
        assert call_kwargs["return_all_parses"] is True

    def test_analyze_invalid_mode(self, client: TestClient) -> None:
        """Test analysis with invalid mode."""
        response = client.post(
            "/api/v1/analyze",
            json={"text": "test", "mode": "invalid"},
        )
        assert response.status_code == 400
        assert "Invalid mode" in response.json()["detail"]

    def test_analyze_empty_text(self, client: TestClient) -> None:
        """Test analysis with empty text."""
        response = client.post(
            "/api/v1/analyze",
            json={"text": ""},
        )
        assert response.status_code == 422  # Validation error

    def test_analyze_with_context(self, client: TestClient, mock_analyzer: MagicMock) -> None:
        """Test analysis with context."""
        response = client.post(
            "/api/v1/analyze",
            json={"text": "test", "context": "From Ramayana"},
        )
        assert response.status_code == 200

        call_kwargs = mock_analyzer.analyze.call_args[1]
        assert call_kwargs["context"] == "From Ramayana"

    def test_analyze_with_engines(self, client: TestClient, mock_analyzer: MagicMock) -> None:
        """Test analysis with specific engines."""
        response = client.post(
            "/api/v1/analyze",
            json={"text": "test", "engines": ["vidyut"]},
        )
        assert response.status_code == 200

        call_kwargs = mock_analyzer.analyze.call_args[1]
        assert call_kwargs["engines"] == ["vidyut"]

    def test_analyze_bypass_cache(self, client: TestClient, mock_analyzer: MagicMock) -> None:
        """Test analysis bypassing cache."""
        response = client.post(
            "/api/v1/analyze",
            json={"text": "test", "bypass_cache": True},
        )
        assert response.status_code == 200

        call_kwargs = mock_analyzer.analyze.call_args[1]
        assert call_kwargs["bypass_cache"] is True


class TestGetAnalysisEndpoint:
    """Tests for GET /api/v1/analyze/{sentence_id}."""

    def test_get_analysis_no_cache(self, client: TestClient) -> None:
        """Test getting analysis when cache not enabled."""
        response = client.get("/api/v1/analyze/test-123")
        assert response.status_code == 404
        assert "Caching not enabled" in response.json()["detail"]

    def test_get_analysis_not_found(
        self,
        config: Config,
        mock_analyzer: MagicMock,
    ) -> None:
        """Test getting analysis that doesn't exist."""
        # Set up cache with sqlite
        mock_cache = MagicMock()
        mock_sqlite = MagicMock()
        mock_sqlite.get_by_id = MagicMock(return_value=None)
        mock_cache._sqlite = mock_sqlite
        mock_analyzer._cache = mock_cache

        app = create_app(config)
        app.state.analyzer = mock_analyzer
        app.state.config = config
        client = TestClient(app)

        response = client.get("/api/v1/analyze/nonexistent")
        assert response.status_code == 404
        assert "Analysis not found" in response.json()["detail"]


class TestDisambiguateEndpoint:
    """Tests for POST /api/v1/disambiguate."""

    def test_disambiguate_no_cache(self, client: TestClient) -> None:
        """Test disambiguation when cache not enabled."""
        response = client.post(
            "/api/v1/disambiguate",
            json={"sentence_id": "test-123", "selected_parse": "p1"},
        )
        assert response.status_code == 400
        assert "Corpus storage not enabled" in response.json()["detail"]


class TestResponseStructure:
    """Tests for response structure."""

    def test_scripts_in_response(self, client: TestClient) -> None:
        """Test scripts are properly formatted."""
        response = client.post(
            "/api/v1/analyze",
            json={"text": "test"},
        )
        assert response.status_code == 200

        scripts = response.json()["scripts"]
        assert "devanagari" in scripts
        assert "iast" in scripts
        assert "slp1" in scripts

    def test_confidence_in_response(self, client: TestClient) -> None:
        """Test confidence metrics are included."""
        response = client.post(
            "/api/v1/analyze",
            json={"text": "test"},
        )
        assert response.status_code == 200

        confidence = response.json()["confidence"]
        assert "overall" in confidence
        assert "engine_agreement" in confidence

    def test_parse_forest_structure(self, client: TestClient) -> None:
        """Test parse forest structure."""
        response = client.post(
            "/api/v1/analyze",
            json={"text": "test"},
        )
        assert response.status_code == 200

        forest = response.json()["parse_forest"]
        assert len(forest) > 0

        parse = forest[0]
        assert "parse_id" in parse
        assert "confidence" in parse
        assert "sandhi_groups" in parse

        group = parse["sandhi_groups"][0]
        assert "group_id" in group
        assert "surface_form" in group
        assert "base_words" in group

        word = group["base_words"][0]
        assert "word_id" in word
        assert "lemma" in word
        assert "confidence" in word
