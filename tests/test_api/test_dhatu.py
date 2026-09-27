"""Tests for dhatu API endpoints, backed by the Dhātupāṭha."""

import pytest
from fastapi.testclient import TestClient

from sanskrit_analyzer.api.app import create_app
from sanskrit_analyzer.config import Config
from sanskrit_analyzer.dhatu import conjugation
from tests._cases import check_cases

needs_vidyut = pytest.mark.skipif(
    not conjugation.is_available(), reason="vidyut data bundle not available"
)


@pytest.fixture
def client() -> TestClient:
    config = Config()
    config.engines.vidyut = False
    return TestClient(create_app(config))


def test_lookup(client: TestClient) -> None:
    """GET /api/v1/dhatu/{dhatu}."""
    response = client.get("/api/v1/dhatu/गम्")
    assert response.status_code == 200
    data = response.json()
    assert data["count"] == 1
    entry = data["dhatus"][0]
    assert entry["root_devanagari"] == "गम्"
    assert entry["code"] == "01.1137"
    assert entry["gana"] == 1
    assert entry["artha_iast"] == "gatau"
    for field in (
        "root_slp1", "root_iast", "upadesha_slp1", "gana_name", "curated",
        "conjugations",
    ):
        assert field in entry

    # The same root reached through IAST and SLP1 gives the same entry.
    iast = client.get("/api/v1/dhatu/bhū").json()
    assert iast == client.get("/api/v1/dhatu/BU").json()
    assert {e["code"] for e in iast["dhatus"]} >= {"01.0001"}

    # The Dhātupāṭha citation form resolves to its root.
    response = client.get("/api/v1/dhatu/ḍukṛñ")
    assert response.status_code == 200
    assert all(e["root_slp1"] == "kf" for e in response.json()["dhatus"])

    # √kṛ is in both the 5th and 8th gaṇa, so both entries come back.
    data = client.get("/api/v1/dhatu/kṛ").json()
    assert data["count"] >= 2
    assert {e["gana"] for e in data["dhatus"]} >= {5, 8}


# (row id, method, path, JSON body, status, substring the lowercased detail holds)
REJECT_CASES = [
    ("unknown-root-404", "get", "/api/v1/dhatu/xxxxxxx", None, 404, "not found"),
    ("unknown-lakara-400", "get",
     "/api/v1/dhatu/गम्?include_conjugations=true&lakara=nope", None, 400, "lakara"),
    ("gana-0-out-of-range", "get", "/api/v1/dhatu/gana/0", None, 400,
     "gana must be between"),
    ("gana-11-out-of-range", "get", "/api/v1/dhatu/gana/11", None, 400,
     "gana must be between"),
]


def test_bad_requests_rejected(client: TestClient) -> None:
    def check(method, path, body, status, needle):
        kwargs = {"json": body} if body is not None else {}
        response = getattr(client, method)(path, **kwargs)
        assert response.status_code == status
        assert needle in response.json()["detail"].lower()

    check_cases(REJECT_CASES, check)


@needs_vidyut
def test_lookup_with_conjugations(client: TestClient) -> None:
    """Conjugations are derived, not stored, so they are actually populated."""
    response = client.get("/api/v1/dhatu/गम्?include_conjugations=true")
    assert response.status_code == 200
    entry = response.json()["dhatus"][0]
    assert entry["padas"] == ["parasmaipada"]
    forms = {(c["purusha"], c["vacana"]): c["forms_iast"] for c in entry["conjugations"]}
    assert forms[("prathama", "eka")] == ["gacchati"]
    assert forms[("uttama", "bahu")] == ["gacchāmaḥ"]

    # A non-default lakāra derives a different paradigm.
    response = client.get("/api/v1/dhatu/गम्?include_conjugations=true&lakara=lrt")
    assert response.status_code == 200
    entry = response.json()["dhatus"][0]
    assert all(c["lakara"] == "lrt" for c in entry["conjugations"])
    assert entry["conjugations"][0]["forms_iast"] == ["gamiṣyati"]


def test_by_gana(client: TestClient) -> None:
    """GET /api/v1/dhatu/gana/{gana}."""
    response = client.get("/api/v1/dhatu/gana/1?limit=10")
    assert response.status_code == 200
    data = response.json()
    assert data["count"] == 10
    assert all(d["gana"] == 1 for d in data["dhatus"])
    assert data["dhatus"][0]["code"]


def test_search(client: TestClient) -> None:
    """POST /api/v1/dhatu/search."""

    def search(**body):
        response = client.post("/api/v1/dhatu/search", json=body)
        assert response.status_code == 200
        return response.json()

    # Search by the Dhātupāṭha's own Sanskrit gloss.
    data = search(query="gatau", search_type="meaning")
    assert data["count"] > 0
    assert all("gatau" in d["artha_iast"] for d in data["dhatus"])

    data = search(query="गम्", search_type="dhatu")
    assert data["count"] == 1
    assert data["dhatus"][0]["root_devanagari"] == "गम्"

    assert search(query="pac", search_type="all")["count"] > 0
    assert search(query="a", search_type="meaning", limit=5)["count"] == 5


def test_stats(client: TestClient) -> None:
    """Stats cover the whole Dhātupāṭha, not a handful of sample roots."""
    response = client.get("/api/v1/dhatu/stats")
    assert response.status_code == 200
    data = response.json()
    assert data["total_dhatus"] > 2000
    assert sorted(int(g) for g in data["gana_counts"]) == list(range(1, 11))
    assert sum(data["gana_counts"].values()) == data["total_dhatus"]
