"""Tests for dhatu API endpoints, backed by the Dhātupāṭha."""

import pytest
from fastapi.testclient import TestClient

from sanskrit_analyzer.api.app import create_app
from sanskrit_analyzer.config import Config
from sanskrit_analyzer.dhatu import conjugation

needs_vidyut = pytest.mark.skipif(
    not conjugation.is_available(), reason="vidyut data bundle not available"
)


@pytest.fixture
def config() -> Config:
    """Create test config."""
    config = Config()
    config.engines.vidyut = False
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
        assert data["count"] == 1
        entry = data["dhatus"][0]
        assert entry["root_devanagari"] == "गम्"
        assert entry["code"] == "01.1137"
        assert entry["gana"] == 1
        assert entry["artha_iast"] == "gatau"

    def test_lookup_iast_and_slp1_agree(self, client: TestClient) -> None:
        """The same root reached through IAST and SLP1 gives the same entry."""
        iast = client.get("/api/v1/dhatu/bhū").json()
        slp1 = client.get("/api/v1/dhatu/BU").json()
        assert iast == slp1
        assert {e["code"] for e in iast["dhatus"]} >= {"01.0001"}

    def test_lookup_citation_form(self, client: TestClient) -> None:
        """The Dhātupāṭha citation form resolves to its root."""
        response = client.get("/api/v1/dhatu/ḍukṛñ")
        assert response.status_code == 200
        assert all(e["root_slp1"] == "kf" for e in response.json()["dhatus"])

    def test_lookup_returns_every_homonymous_entry(self, client: TestClient) -> None:
        """√kṛ is in both the 5th and 8th gaṇa, so both entries come back."""
        data = client.get("/api/v1/dhatu/kṛ").json()
        assert data["count"] >= 2
        assert {e["gana"] for e in data["dhatus"]} >= {5, 8}

    def test_lookup_not_found(self, client: TestClient) -> None:
        """Test looking up nonexistent dhatu."""
        response = client.get("/api/v1/dhatu/xxxxxxx")
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    @needs_vidyut
    def test_lookup_with_conjugations(self, client: TestClient) -> None:
        """Conjugations are derived, not stored, so they are actually populated."""
        response = client.get("/api/v1/dhatu/गम्?include_conjugations=true")
        assert response.status_code == 200

        entry = response.json()["dhatus"][0]
        assert entry["padas"] == ["parasmaipada"]
        forms = {
            (c["purusha"], c["vacana"]): c["forms_iast"] for c in entry["conjugations"]
        }
        assert forms[("prathama", "eka")] == ["gacchati"]
        assert forms[("uttama", "bahu")] == ["gacchāmaḥ"]

    @needs_vidyut
    def test_conjugations_in_another_lakara(self, client: TestClient) -> None:
        """A non-default lakāra derives a different paradigm."""
        response = client.get("/api/v1/dhatu/गम्?include_conjugations=true&lakara=lrt")
        assert response.status_code == 200
        entry = response.json()["dhatus"][0]
        assert all(c["lakara"] == "lrt" for c in entry["conjugations"])
        assert entry["conjugations"][0]["forms_iast"] == ["gamiṣyati"]

    def test_unknown_lakara_rejected(self, client: TestClient) -> None:
        response = client.get("/api/v1/dhatu/गम्?include_conjugations=true&lakara=nope")
        assert response.status_code == 400
        assert "lakara" in response.json()["detail"].lower()


class TestDhatuByGana:
    """Tests for GET /api/v1/dhatu/gana/{gana}."""

    def test_get_gana_1(self, client: TestClient) -> None:
        """Test getting gana 1 dhatus."""
        response = client.get("/api/v1/dhatu/gana/1?limit=10")
        assert response.status_code == 200

        data = response.json()
        assert data["count"] == 10
        assert all(d["gana"] == 1 for d in data["dhatus"])

    def test_get_invalid_gana(self, client: TestClient) -> None:
        """Test getting invalid gana."""
        response = client.get("/api/v1/dhatu/gana/0")
        assert response.status_code == 400
        assert "Gana must be between" in response.json()["detail"]

        response = client.get("/api/v1/dhatu/gana/11")
        assert response.status_code == 400


class TestDhatuSearch:
    """Tests for POST /api/v1/dhatu/search."""

    def test_search_by_artha(self, client: TestClient) -> None:
        """Search by the Dhātupāṭha's own Sanskrit gloss."""
        response = client.post(
            "/api/v1/dhatu/search",
            json={"query": "gatau", "search_type": "meaning"},
        )
        assert response.status_code == 200

        data = response.json()
        assert data["count"] > 0
        assert all("gatau" in d["artha_iast"] for d in data["dhatus"])

    def test_search_by_dhatu(self, client: TestClient) -> None:
        """Test searching by dhatu form."""
        response = client.post(
            "/api/v1/dhatu/search",
            json={"query": "गम्", "search_type": "dhatu"},
        )
        assert response.status_code == 200

        data = response.json()
        assert data["count"] == 1
        assert data["dhatus"][0]["root_devanagari"] == "गम्"

    def test_search_all(self, client: TestClient) -> None:
        """Test searching all fields."""
        response = client.post(
            "/api/v1/dhatu/search",
            json={"query": "pac", "search_type": "all"},
        )
        assert response.status_code == 200
        assert response.json()["count"] > 0

    def test_search_with_limit(self, client: TestClient) -> None:
        """Test search respects limit."""
        response = client.post(
            "/api/v1/dhatu/search",
            json={"query": "a", "search_type": "meaning", "limit": 5},
        )
        assert response.status_code == 200
        assert response.json()["count"] == 5


class TestDhatuStats:
    """Tests for GET /api/v1/dhatu/stats."""

    def test_get_stats(self, client: TestClient) -> None:
        """Stats cover the whole Dhātupāṭha, not a handful of sample roots."""
        response = client.get("/api/v1/dhatu/stats")
        assert response.status_code == 200

        data = response.json()
        assert data["total_dhatus"] > 2000
        assert sorted(int(g) for g in data["gana_counts"]) == list(range(1, 11))
        assert sum(data["gana_counts"].values()) == data["total_dhatus"]


class TestDhatuResponseStructure:
    """Tests for response structure."""

    def test_dhatu_fields(self, client: TestClient) -> None:
        """Test dhatu response has all expected fields."""
        data = client.get("/api/v1/dhatu/गम्").json()["dhatus"][0]
        for field in (
            "code",
            "root_slp1",
            "root_iast",
            "root_devanagari",
            "upadesha_slp1",
            "gana",
            "gana_name",
            "artha_iast",
            "curated",
            "conjugations",
        ):
            assert field in data

    def test_list_response_structure(self, client: TestClient) -> None:
        """Test list response structure."""
        data = client.get("/api/v1/dhatu/gana/1?limit=5").json()
        assert isinstance(data["count"], int)
        assert isinstance(data["dhatus"], list)
        assert data["dhatus"][0]["code"]
