"""Tests for dhatu API endpoints."""

import pytest
from fastapi.testclient import TestClient

from sanskrit_analyzer.api.app import create_app
from sanskrit_analyzer.config import Config


@pytest.fixture
def config() -> Config:
    """Create test config."""
    config = Config()
    config.engines.vidyut = False
    config.engines.dharmamitra = False
    config.engines.heritage = False
    return config


@pytest.fixture
def client(config: Config) -> TestClient:
    """Create test client."""
    app = create_app(config)
    return TestClient(app)


class TestDhatuLookup:
    """Tests for GET /api/v1/dhatu/{dhatu}."""

    def test_lookup_devanagari(self, client: TestClient) -> None:
        """Test looking up dhatu by Devanagari."""
        response = client.get("/api/v1/dhatu/गम्")
        assert response.status_code == 200

        data = response.json()
        assert data["dhatu_devanagari"] == "गम्"
        assert "go" in data["meaning_english"].lower()

    def test_lookup_not_found(self, client: TestClient) -> None:
        """Test looking up nonexistent dhatu."""
        response = client.get("/api/v1/dhatu/xxxxxxx")
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    def test_lookup_with_conjugations(self, client: TestClient) -> None:
        """Test looking up dhatu with conjugations."""
        response = client.get("/api/v1/dhatu/गम्?include_conjugations=true")
        assert response.status_code == 200

        data = response.json()
        # Conjugations list should exist (may be empty)
        assert "conjugations" in data
        assert isinstance(data["conjugations"], list)


class TestDhatuByGana:
    """Tests for GET /api/v1/dhatu/gana/{gana}."""

    def test_get_gana_1(self, client: TestClient) -> None:
        """Test getting gana 1 dhatus."""
        response = client.get("/api/v1/dhatu/gana/1?limit=10")
        assert response.status_code == 200

        data = response.json()
        assert "count" in data
        assert "dhatus" in data
        assert data["count"] <= 10
        # All dhatus should be gana 1
        for dhatu in data["dhatus"]:
            if dhatu["gana"] is not None:
                assert dhatu["gana"] == 1

    def test_get_invalid_gana(self, client: TestClient) -> None:
        """Test getting invalid gana."""
        response = client.get("/api/v1/dhatu/gana/0")
        assert response.status_code == 400
        assert "Gana must be between" in response.json()["detail"]

        response = client.get("/api/v1/dhatu/gana/11")
        assert response.status_code == 400


class TestDhatuSearch:
    """Tests for POST /api/v1/dhatu/search."""

    def test_search_by_meaning(self, client: TestClient) -> None:
        """Test searching by English meaning."""
        response = client.post(
            "/api/v1/dhatu/search",
            json={"query": "go", "search_type": "meaning"},
        )
        assert response.status_code == 200

        data = response.json()
        assert data["count"] > 0
        # At least one should contain "go" in meaning
        assert any("go" in (d["meaning_english"] or "").lower() for d in data["dhatus"])

    def test_search_by_dhatu(self, client: TestClient) -> None:
        """Test searching by dhatu form."""
        response = client.post(
            "/api/v1/dhatu/search",
            json={"query": "गम्", "search_type": "dhatu"},
        )
        assert response.status_code == 200

        data = response.json()
        assert data["count"] == 1
        assert data["dhatus"][0]["dhatu_devanagari"] == "गम्"

    def test_search_all(self, client: TestClient) -> None:
        """Test searching all fields."""
        response = client.post(
            "/api/v1/dhatu/search",
            json={"query": "to do", "search_type": "all"},
        )
        assert response.status_code == 200

        data = response.json()
        assert data["count"] >= 0  # May or may not find matches

    def test_search_with_limit(self, client: TestClient) -> None:
        """Test search respects limit."""
        response = client.post(
            "/api/v1/dhatu/search",
            json={"query": "to", "search_type": "meaning", "limit": 5},
        )
        assert response.status_code == 200

        data = response.json()
        assert data["count"] <= 5


class TestDhatuStats:
    """Tests for GET /api/v1/dhatu/stats."""

    def test_get_stats(self, client: TestClient) -> None:
        """Test getting dhatu statistics."""
        response = client.get("/api/v1/dhatu/stats")
        assert response.status_code == 200

        data = response.json()
        assert "total_dhatus" in data
        assert "gana_counts" in data
        assert data["total_dhatus"] > 0
        assert isinstance(data["gana_counts"], dict)


class TestDhatuResponseStructure:
    """Tests for response structure."""

    def test_dhatu_fields(self, client: TestClient) -> None:
        """Test dhatu response has all expected fields."""
        response = client.get("/api/v1/dhatu/गम्")
        assert response.status_code == 200

        data = response.json()
        assert "id" in data
        assert "dhatu_devanagari" in data
        assert "meaning_english" in data
        assert "gana" in data
        assert "pada" in data
        assert "conjugations" in data

    def test_list_response_structure(self, client: TestClient) -> None:
        """Test list response structure."""
        response = client.get("/api/v1/dhatu/gana/1?limit=5")
        assert response.status_code == 200

        data = response.json()
        assert isinstance(data["count"], int)
        assert isinstance(data["dhatus"], list)
        if data["dhatus"]:
            assert "id" in data["dhatus"][0]
            assert "dhatu_devanagari" in data["dhatus"][0]
