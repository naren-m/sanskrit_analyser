"""Tests for the engine runner."""

import asyncio
from unittest.mock import AsyncMock

import pytest

from sanskrit_analyzer.engines.base import EngineBase, EngineResult, Segment
from sanskrit_analyzer.engines.runner import AnalyzedSegment, EngineRunner
from tests._cases import check_cases


class MockEngine(EngineBase):
    """Mock engine for testing."""

    def __init__(
        self,
        name: str,
        segments: list[Segment] | None = None,
        available: bool = True,
    ) -> None:
        self._name = name
        self._segments = segments or []
        self._available = available

    @property
    def name(self) -> str:
        return self._name

    @property
    def is_available(self) -> bool:
        return self._available

    async def analyze(self, text: str) -> EngineResult:
        return EngineResult(
            engine=self._name,
            segments=self._segments,
            confidence=0.9 if self._segments else 0.0,
        )


def _gam() -> Segment:
    return Segment(surface="gacchati", lemma="gam", confidence=0.9)


def _failing(name: str = "failing") -> MockEngine:
    engine = MockEngine(name)
    engine.analyze = AsyncMock(side_effect=Exception("Test error"))
    return engine


def _mutate(runner: EngineRunner, op: str) -> list[str]:
    if op == "add":
        runner.add_engine(MockEngine("test"))
        return runner.engine_names
    if op == "remove":
        runner.remove_engine("vidyut")
        return runner.engine_names
    return runner.available_engines


# (id, engines, operation, expected names)
ENGINE_LIST_CASES = [
    ("add_engine appends to engine_names", [], "add", ["test"]),
    (
        "remove_engine drops only the named engine",
        [MockEngine("vidyut", [_gam()]), MockEngine("local_byt5", [_gam()])],
        "remove",
        ["local_byt5"],
    ),
    (
        "available_engines excludes unavailable ones",
        [MockEngine("available", available=True), MockEngine("unavailable", available=False)],
        "available",
        ["available"],
    ),
]

# (id, engine factory, analyze kwargs, expected attributes of the result)
# Expected keys: success, primary, lemmas, confidence, ran (engine_results keys),
# votes/agreement (first segment), error_in (substring of some error), errors
# (exact list), names_after (runner.engine_names after the call).
ANALYZE_CASES = [
    (
        "single engine: its segments and confidence are the result",
        lambda: [MockEngine("vidyut", [_gam()])],
        {},
        {"success": True, "primary": "vidyut", "lemmas": ["gam"], "confidence": 0.9},
    ),
    (
        "no weighting: the vote is the engine's own confidence",
        lambda: [MockEngine("vidyut", [_gam()])],
        {},
        {"votes": {"vidyut": 0.9}, "agreement": 1.0},
    ),
    (
        # The slower fallback never runs once the primary has segments.
        "first configured engine wins even when a later one splits more",
        lambda: [
            MockEngine("vidyut", [Segment(surface="test", lemma="first", confidence=0.6)]),
            MockEngine(
                "local_byt5",
                [
                    Segment(surface="te", lemma="second_a", confidence=0.99),
                    Segment(surface="st", lemma="second_b", confidence=0.99),
                ],
            ),
        ],
        {},
        {"primary": "vidyut", "lemmas": ["first"], "ran": {"vidyut"}},
    ),
    (
        "primary skips an engine with no segments",
        lambda: [MockEngine("empty", []), MockEngine("vidyut", [_gam()])],
        {},
        {"success": True, "primary": "vidyut"},
    ),
    (
        "no engines configured fails",
        lambda: [],
        {},
        {"success": False, "error_in": "No engines configured"},
    ),
    (
        "all engines unavailable fails",
        lambda: [MockEngine("test", available=False)],
        {},
        {"success": False, "error_in": "No available engines"},
    ),
    (
        "an engine exception is recorded and the next engine is used",
        lambda: [_failing(), MockEngine("working", [_gam()])],
        {},
        {"success": True, "primary": "working", "error_in": "Test error"},
    ),
    (
        "all engines failing reports their errors",
        lambda: [_failing()],
        {},
        {"success": False, "error_in": "Test error"},
    ),
    (
        "engines= filter restricts one call without mutating the shared list",
        lambda: [MockEngine("vidyut", [_gam()]), MockEngine("local_byt5", [_gam()])],
        {"engines": ["local_byt5"]},
        {"ran": {"local_byt5"}, "names_after": ["vidyut", "local_byt5"]},
    ),
    (
        "engines= filter with no match reports no engines",
        lambda: [MockEngine("vidyut", [])],
        {"engines": ["nope"]},
        {"errors": ["No engines configured"]},
    ),
]


def test_engine_list_management() -> None:
    def check(engines, op, expected):
        assert _mutate(EngineRunner(engines=engines), op) == expected

    check_cases(ENGINE_LIST_CASES, check)


def test_create_default() -> None:
    try:
        runner = EngineRunner.create_default()
    except ImportError:
        pytest.skip("Default engines not available")
    assert runner.engine_names == ["vidyut"]


def test_analyze() -> None:
    def check(make_engines, kwargs, expect):
        runner = EngineRunner(engines=make_engines())
        result = asyncio.run(runner.analyze("gacchati", **kwargs))
        if "success" in expect:
            assert result.success is expect["success"], result.errors
        if "primary" in expect:
            assert result.primary_engine == expect["primary"]
        if "lemmas" in expect:
            assert [s.lemma for s in result.segments] == expect["lemmas"]
        if "confidence" in expect:
            assert result.overall_confidence == pytest.approx(expect["confidence"])
        if "ran" in expect:
            assert set(result.engine_results) == expect["ran"]
        if "votes" in expect:
            assert result.segments[0].engine_votes == expect["votes"]
            assert result.segments[0].agreement_score == expect["agreement"]
        if "error_in" in expect:
            assert any(expect["error_in"] in e for e in result.errors), result.errors
        if "errors" in expect:
            assert result.errors == expect["errors"]
        if "names_after" in expect:
            assert runner.engine_names == expect["names_after"]

    check_cases(ANALYZE_CASES, check)


def test_analyzed_segment_from_segment() -> None:
    """from_segment records the engine vote and never aliases the engine's list."""
    source = Segment(
        surface="test",
        lemma="lemma",
        morphology="noun",
        confidence=0.9,
        pos="noun",
        meanings=["meaning"],
    )
    analyzed = AnalyzedSegment.from_segment(source, "vidyut")

    assert (analyzed.surface, analyzed.lemma, analyzed.morphology, analyzed.pos) == (
        "test",
        "lemma",
        "noun",
        "noun",
    )
    assert analyzed.confidence == 0.9
    assert analyzed.meanings == ["meaning"]
    assert analyzed.engine_votes == {"vidyut": 0.9}
    assert analyzed.agreement_score == 1.0

    analyzed.meanings.append("added")
    assert source.meanings == ["meaning"]
