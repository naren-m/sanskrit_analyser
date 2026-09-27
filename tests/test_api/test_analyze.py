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
from tests._cases import check_cases


@pytest.fixture
def config() -> Config:
    """Create test config."""
    config = Config()
    config.engines.vidyut = False
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
    analyzer.get_available_engines = MagicMock(return_value=["vidyut"])
    analyzer._cache = None
    return analyzer


@pytest.fixture
def client(config: Config, mock_analyzer: MagicMock) -> TestClient:
    """Create test client."""
    app = create_app(config)
    app.state.analyzer = mock_analyzer
    app.state.config = config
    return TestClient(app)


def _post(client: TestClient, **body):
    return client.post("/api/v1/analyze", json={"text": "test", **body})


def test_analyze_returns_tree(client: TestClient) -> None:
    response = client.post("/api/v1/analyze", json={"text": "रामः गच्छति"})
    assert response.status_code == 200

    data = response.json()
    assert data["sentence_id"] == "test-123"
    assert data["original_text"] == "रामः गच्छति"
    assert data["normalized_slp1"] == "rAmaH gacCati"
    assert len(data["parse_forest"]) == 1

    assert {"devanagari", "iast", "slp1"} <= set(data["scripts"])
    assert {"overall", "engine_agreement"} <= set(data["confidence"])
    parse = data["parse_forest"][0]
    assert {"parse_id", "confidence", "sandhi_groups"} <= set(parse)
    group = parse["sandhi_groups"][0]
    assert {"group_id", "surface_form", "base_words"} <= set(group)
    assert {"word_id", "lemma", "confidence"} <= set(group["base_words"][0])


# (row id, request fields, analyzer kwarg, expected kwarg value); the route
# translates request JSON into Analyzer.analyze kwargs (mode str -> enum).
FORWARD_CASES = [
    ("mode-string-becomes-enum", {"mode": "educational"}, "mode", "educational"),
    ("return-all-parses", {"return_all_parses": True}, "return_all_parses", True),
    ("context", {"context": "From Ramayana"}, "context", "From Ramayana"),
    ("engines", {"engines": ["vidyut"]}, "engines", ["vidyut"]),
    ("bypass-cache", {"bypass_cache": True}, "bypass_cache", True),
]


def test_request_fields_reach_analyzer(
    client: TestClient, mock_analyzer: MagicMock
) -> None:
    def check(body, kwarg, expected):
        assert _post(client, **body).status_code == 200
        got = mock_analyzer.analyze.call_args[1][kwarg]
        if kwarg == "mode":
            got = str(got.value)
        # type check keeps the original `is True` strictness for bool flags
        assert got == expected and type(got) is type(expected), got

    check_cases(FORWARD_CASES, check)


# (row id, request body, status, substrings the detail must contain)
REJECT_CASES = [
    ("invalid-mode-400", {"text": "test", "mode": "invalid"}, 400, ["Invalid mode"]),
    ("empty-text-422-validation", {"text": ""}, 422, []),
    ("unknown-engine-400-names-it", {"text": "test", "engines": ["bogus"]}, 400,
     ["Unknown engine", "bogus"]),
]


def test_bad_requests_rejected(client: TestClient) -> None:
    def check(body, status, needles):
        response = client.post("/api/v1/analyze", json=body)
        assert response.status_code == status
        for needle in needles:
            assert needle in response.json()["detail"]

    check_cases(REJECT_CASES, check)


def test_analyze_engine_failure(client: TestClient, mock_analyzer: MagicMock) -> None:
    """Engine failure on valid input maps to a structured 500."""
    mock_analyzer.analyze = AsyncMock(side_effect=RuntimeError("engine exploded"))
    response = _post(client)
    assert response.status_code == 500
    assert response.json()["detail"] == "Analysis failed"  # no exception text leaked
