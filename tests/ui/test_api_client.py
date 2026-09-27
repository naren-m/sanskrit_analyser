"""Tests for the Sanskrit Analyzer API client.

HTTP is faked at the ``httpx.AsyncClient`` boundary; everything behind it
(response transform, error mapping) is the real client.
"""

import asyncio
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import httpx

from sanskrit_analyzer.ui.api_client import (
    SanskritAPIClient,
    _coerce_confidence,
    _transform_api_response,
)
from tests._cases import check_cases

# Full API-shaped response: exercises group, base-word and dhatu transforms.
SAMPLE_ANALYSIS_RESPONSE = {
    "original_text": "रामः गच्छति",
    "scripts": {
        "devanagari": "रामः गच्छति",
        "iast": "rāmaḥ gacchati",
        "slp1": "rAmaH gacCati",
    },
    "confidence": {"overall": 0.94, "engine_agreement": 0.85},
    "mode": "educational",
    "parse_forest": [
        {
            "parse_id": "parse_1",
            "confidence": 0.94,
            "sandhi_groups": [
                {
                    "group_id": "g0_0",
                    "surface_form": "rAmaH",
                    "base_words": [
                        {
                            "word_id": "w0_0_0",
                            "lemma": "rAma",
                            "surface_form": "rAmaH",
                            "scripts": {"devanagari": "राम", "iast": "rāma"},
                            "morphology": {"pos": "noun", "case": "nominative"},
                            "meanings": ["Rama", "pleasing"],
                            "confidence": 0.95,
                        }
                    ],
                },
                {
                    "group_id": "g0_1",
                    "surface_form": "gacCati",
                    "base_words": [
                        {
                            "word_id": "w0_1_0",
                            "lemma": "gam",
                            "surface_form": "gacCati",
                            "scripts": {"devanagari": "गम्", "iast": "gam"},
                            "morphology": {"pos": "verb", "person": "3rd"},
                            "meanings": ["goes"],
                            "dhatu": {"dhatu": "gam", "meaning": "to go", "gana": 1},
                            "confidence": 0.93,
                        }
                    ],
                },
            ],
        }
    ],
}

COERCE_CASES = [
    ("None defaults to 0.0", None, 0.0),
    ("non-numeric defaults to 0.0", "not-a-number", 0.0),
    ("float passes through", 0.75, 0.75),
    ("int becomes float", 1, 1.0),
]

G0 = ("parses", 0, "sandhi_groups", 0)

# (id, API payload, {path into the transformed dict: expected value})
TRANSFORM_CASES = [
    ("null overall confidence becomes 0.0, not None", {"confidence": None}, {("confidence",): 0.0}),
    (
        "null parse confidence becomes 0.0",
        {"parse_forest": [{"parse_id": "p1", "confidence": None}]},
        {("parses", 0, "confidence"): 0.0},
    ),
    (
        "engine_votes survives on the parse",
        {"parse_forest": [{"parse_id": "p1", "engine_votes": {"vidyut": 0.9}}]},
        {("parses", 0, "engine_votes"): {"vidyut": 0.9}},
    ),
    (
        "sandhi_type, is_compound and compound_type survive on the group",
        {
            "parse_forest": [
                {
                    "parse_id": "p1",
                    "sandhi_groups": [
                        {
                            "group_id": "g0",
                            "surface_form": "x",
                            "sandhi_type": "visarga",
                            "is_compound": True,
                            "compound_type": "tatpurusha",
                        }
                    ],
                }
            ]
        },
        {
            (*G0, "sandhi_type"): "visarga",
            (*G0, "is_compound"): True,
            (*G0, "compound_type"): "tatpurusha",
        },
    ),
]


def _response(
    status: int, body: Any = None, *, text: str = "", json_error: Exception | None = None
):
    resp = MagicMock()
    resp.status_code = status
    resp.text = text
    if json_error is not None:
        resp.json.side_effect = json_error
    else:
        resp.json.return_value = body
    return resp


# (id, call, response or exception raised by httpx, expected outcome)
# Outcome keys: success, data (subset of result.data), parses (count),
# error (substring of error.message), mode (sent in the request body).
HTTP_CASES = [
    (
        "analyze 200 transforms API shape to UI shape",
        ("analyze", "educational"),
        _response(
            200,
            {
                "original_text": "रामः गच्छति",
                "scripts": {"devanagari": "रामः गच्छति", "iast": "rāmaḥ gacchati"},
                "parse_forest": [],
                "confidence": {"overall": 0.95},
                "mode": "educational",
            },
        ),
        {
            "success": True,
            "data": {
                "sentence": {
                    "original": "रामः गच्छति",
                    "scripts": {"devanagari": "रामः गच्छति", "iast": "rāmaḥ gacchati"},
                },
                "confidence": 0.95,
                "parses": [],
            },
        },
    ),
    (
        "analyze 200 with a full parse forest keeps every parse",
        ("analyze", "educational"),
        _response(200, SAMPLE_ANALYSIS_RESPONSE),
        {
            "success": True,
            "data": {
                "sentence": {
                    "original": "रामः गच्छति",
                    "scripts": SAMPLE_ANALYSIS_RESPONSE["scripts"],
                }
            },
            "parses": 1,
        },
    ),
    (
        "educational mode is sent in the request",
        ("analyze", "educational"),
        _response(200, SAMPLE_ANALYSIS_RESPONSE),
        {"mode": "educational"},
    ),
    (
        "research mode is sent in the request",
        ("analyze", "research"),
        _response(200, SAMPLE_ANALYSIS_RESPONSE),
        {"mode": "research"},
    ),
    (
        "quick mode is sent in the request",
        ("analyze", "quick"),
        _response(200, SAMPLE_ANALYSIS_RESPONSE),
        {"mode": "quick"},
    ),
    (
        "analyze connect error says Cannot connect",
        ("analyze", "educational"),
        httpx.ConnectError("Connection refused"),
        {"success": False, "error": "Cannot connect"},
    ),
    (
        "analyze timeout says timed out",
        ("analyze", "educational"),
        httpx.TimeoutException("Timeout"),
        {"success": False, "error": "timed out"},
    ),
    (
        "analyze 5xx says Server error",
        ("analyze", "educational"),
        _response(500, {}, text="Internal Server Error"),
        {"success": False, "error": "Server error"},
    ),
    (
        "analyze 200 with non-JSON body returns a structured error, no traceback",
        ("analyze", "educational"),
        _response(200, json_error=ValueError("Expecting value")),
        {"success": False, "error": "Unexpected error"},
    ),
    (
        "health_check 200 returns the body",
        ("health_check",),
        _response(200, {"status": "healthy"}),
        {"success": True, "data": {"status": "healthy"}, "exact": True},
    ),
    (
        "health_check connect error says Cannot connect",
        ("health_check",),
        httpx.ConnectError("Connection refused"),
        {"success": False, "error": "Cannot connect"},
    ),
]


def _call(call: tuple, outcome: Any) -> tuple[Any, AsyncMock]:
    with patch("httpx.AsyncClient") as mock_client:
        http = AsyncMock()
        verb = "post" if call[0] == "analyze" else "get"
        if isinstance(outcome, Exception):
            getattr(http, verb).side_effect = outcome
        else:
            getattr(http, verb).return_value = outcome
        http.__aenter__.return_value = http
        http.__aexit__.return_value = None
        mock_client.return_value = http

        client = SanskritAPIClient()
        if call[0] == "analyze":
            result = asyncio.run(client.analyze("रामः गच्छति", call[1]))
        else:
            result = asyncio.run(client.health_check())
    return result, http


def test_coerce_confidence() -> None:
    def check(value, expected):
        got = _coerce_confidence(value)
        assert got == expected and isinstance(got, float), got

    check_cases(COERCE_CASES, check)


def test_transform_api_response() -> None:
    def check(payload, expected):
        transformed = _transform_api_response(payload)
        for path, want in expected.items():
            node = transformed
            for step in path:
                node = node[step]
            assert node == want, f"{path} = {node!r}, want {want!r}"

    check_cases(TRANSFORM_CASES, check)


def test_http_calls() -> None:
    """analyze() and health_check() map every HTTP outcome to an AnalysisResult."""
    assert "localhost:8000" in SanskritAPIClient().base_url

    def check(call, outcome, expect):
        result, http = _call(call, outcome)
        if "success" in expect:
            assert result.success is expect["success"], result
        if "data" in expect:
            if expect.get("exact"):
                assert result.data == expect["data"]
            else:
                subset = {k: result.data[k] for k in expect["data"]}
                assert subset == expect["data"], subset
        if "parses" in expect:
            assert len(result.data["parses"]) == expect["parses"]
        if "error" in expect:
            assert result.error is not None
            assert expect["error"] in result.error.message, result.error.message
        if "mode" in expect:
            assert http.post.call_args[1]["json"]["mode"] == expect["mode"]

    check_cases(HTTP_CASES, check)
