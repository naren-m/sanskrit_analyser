"""Tests for the MCP dhatu tools, dispatched as a client would call them."""

import json

import pytest

from sanskrit_analyzer.dhatu import conjugation
from sanskrit_analyzer.mcp.tools.dhatu import build_dhatu_tools
from tests._cases import check_cases

needs_vidyut = pytest.mark.skipif(
    not conjugation.is_available(), reason="vidyut data bundle not available"
)


@pytest.fixture(scope="module")
def dispatch():
    _, dispatcher = build_dhatu_tools()
    return dispatcher


async def _call(dispatch, name: str, **arguments):
    result = await dispatch(name, arguments)
    assert result is not None, f"{name} not dispatched"
    return result[0].text


def test_all_four_tools_are_advertised() -> None:
    tools, _ = build_dhatu_tools()
    assert {t.name for t in tools} == {
        "lookup_dhatu",
        "search_dhatu",
        "conjugate_verb",
        "list_gana",
    }


# (row id, tool, arguments, substring the error text must contain)
ERROR_CASES = [
    ("lookup-requires-dhatu", "lookup_dhatu", {}, "Error"),
    ("search-requires-query", "search_dhatu", {}, "Error"),
    ("list-gana-rejects-out-of-range", "list_gana", {"gana": 11}, "Error"),
    ("conjugate-rejects-unknown-lakara", "conjugate_verb",
     {"dhatu": "gam", "lakara": "nope"}, "lakara"),
    ("conjugate-requires-dhatu", "conjugate_verb", {}, "Error"),
]


async def test_bad_arguments_return_errors(dispatch) -> None:
    # Dispatch is async and check_cases is sync: call every row first, then
    # check the collected texts row by row.
    rows = [
        (row_id, await _call(dispatch, tool, **arguments), needle)
        for row_id, tool, arguments, needle in ERROR_CASES
    ]

    def check(text, needle):
        assert text.startswith("Error"), text
        assert needle in text, text

    check_cases(rows, check)
    # An unknown root is a not-found message, not an error.
    assert "not found" in (await _call(dispatch, "lookup_dhatu", dhatu="xyznot")).lower()


async def test_lookup_dhatu(dispatch) -> None:
    entries = json.loads(await _call(dispatch, "lookup_dhatu", dhatu="gam"))
    assert [e["code"] for e in entries] == ["01.1137"]
    assert entries[0]["gana"] == 1
    assert entries[0]["artha_iast"] == "gatau"

    entries = json.loads(await _call(dispatch, "lookup_dhatu", dhatu="पच्"))
    assert all(e["root_slp1"] == "pac" for e in entries)


async def test_search_dhatu(dispatch) -> None:
    results = json.loads(await _call(dispatch, "search_dhatu", query="gatau"))
    assert results
    assert all("gatau" in r["artha_iast"] for r in results)

    results = json.loads(await _call(dispatch, "search_dhatu", query="a", limit=3))
    assert len(results) == 3


async def test_list_gana(dispatch) -> None:
    results = json.loads(await _call(dispatch, "list_gana", gana=2, limit=10))
    assert len(results) == 10
    assert all(r["gana"] == 2 for r in results)

    # The low-level server does not coerce against the schema.
    results = json.loads(await _call(dispatch, "list_gana", gana="3", limit=2))
    assert all(r["gana"] == 3 for r in results)


@needs_vidyut
async def test_conjugate_verb(dispatch) -> None:
    """Conjugation, derived by the Pāṇinian engine."""
    results = json.loads(await _call(dispatch, "conjugate_verb", dhatu="gam"))
    assert len(results) == 1
    assert results[0]["padas"] == ["parasmaipada"]
    forms = {(f["purusha"], f["vacana"]): f["forms_iast"] for f in results[0]["forms"]}
    assert forms[("prathama", "eka")] == ["gacchati"]

    # √nah is ubhayapada, so both padas are derived.
    results = json.loads(await _call(dispatch, "conjugate_verb", dhatu="nah"))
    assert any(r["padas"] == ["parasmaipada", "ātmanepada"] for r in results)
