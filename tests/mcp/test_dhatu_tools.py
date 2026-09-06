"""Tests for the MCP dhatu tools, dispatched as a client would call them."""

import json

import pytest

from sanskrit_analyzer.dhatu import conjugation
from sanskrit_analyzer.mcp.tools.dhatu import build_dhatu_tools

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


class TestToolSpecs:
    """The advertised tools."""

    def test_all_four_tools_are_advertised(self) -> None:
        tools, _ = build_dhatu_tools()
        assert {t.name for t in tools} == {
            "lookup_dhatu",
            "search_dhatu",
            "conjugate_verb",
            "list_gana",
        }


class TestLookupDhatu:
    """Tests for dhatu lookup."""

    @pytest.mark.asyncio
    async def test_lookup_known_dhatu(self, dispatch) -> None:
        entries = json.loads(await _call(dispatch, "lookup_dhatu", dhatu="gam"))
        assert [e["code"] for e in entries] == ["01.1137"]
        assert entries[0]["gana"] == 1
        assert entries[0]["artha_iast"] == "gatau"

    @pytest.mark.asyncio
    async def test_lookup_devanagari(self, dispatch) -> None:
        entries = json.loads(await _call(dispatch, "lookup_dhatu", dhatu="पच्"))
        assert all(e["root_slp1"] == "pac" for e in entries)

    @pytest.mark.asyncio
    async def test_lookup_unknown_dhatu(self, dispatch) -> None:
        assert "not found" in (await _call(dispatch, "lookup_dhatu", dhatu="xyznot")).lower()

    @pytest.mark.asyncio
    async def test_lookup_requires_dhatu(self, dispatch) -> None:
        assert (await _call(dispatch, "lookup_dhatu")).startswith("Error")


class TestSearchDhatu:
    """Tests for dhatu search."""

    @pytest.mark.asyncio
    async def test_search_returns_matches(self, dispatch) -> None:
        results = json.loads(await _call(dispatch, "search_dhatu", query="gatau"))
        assert results
        assert all("gatau" in r["artha_iast"] for r in results)

    @pytest.mark.asyncio
    async def test_search_respects_limit(self, dispatch) -> None:
        results = json.loads(await _call(dispatch, "search_dhatu", query="a", limit=3))
        assert len(results) == 3

    @pytest.mark.asyncio
    async def test_search_requires_query(self, dispatch) -> None:
        assert (await _call(dispatch, "search_dhatu")).startswith("Error")


class TestListGana:
    """Tests for listing dhatus by gana."""

    @pytest.mark.asyncio
    async def test_list_gana(self, dispatch) -> None:
        results = json.loads(await _call(dispatch, "list_gana", gana=2, limit=10))
        assert len(results) == 10
        assert all(r["gana"] == 2 for r in results)

    @pytest.mark.asyncio
    async def test_list_gana_accepts_string(self, dispatch) -> None:
        """The low-level server does not coerce against the schema."""
        results = json.loads(await _call(dispatch, "list_gana", gana="3", limit=2))
        assert all(r["gana"] == 3 for r in results)

    @pytest.mark.asyncio
    async def test_list_gana_rejects_out_of_range(self, dispatch) -> None:
        assert (await _call(dispatch, "list_gana", gana=11)).startswith("Error")


class TestConjugateVerb:
    """Tests for conjugation, derived by the Pāṇinian engine."""

    @pytest.mark.asyncio
    @needs_vidyut
    async def test_conjugate_lat(self, dispatch) -> None:
        results = json.loads(await _call(dispatch, "conjugate_verb", dhatu="gam"))
        assert len(results) == 1
        assert results[0]["padas"] == ["parasmaipada"]
        forms = {
            (f["purusha"], f["vacana"]): f["forms_iast"] for f in results[0]["forms"]
        }
        assert forms[("prathama", "eka")] == ["gacchati"]

    @pytest.mark.asyncio
    @needs_vidyut
    async def test_conjugate_reports_both_padas(self, dispatch) -> None:
        """√nah is ubhayapada, so both padas are derived."""
        results = json.loads(await _call(dispatch, "conjugate_verb", dhatu="nah"))
        assert any(r["padas"] == ["parasmaipada", "ātmanepada"] for r in results)

    @pytest.mark.asyncio
    async def test_conjugate_rejects_unknown_lakara(self, dispatch) -> None:
        text = await _call(dispatch, "conjugate_verb", dhatu="gam", lakara="nope")
        assert text.startswith("Error") and "lakara" in text

    @pytest.mark.asyncio
    async def test_conjugate_requires_dhatu(self, dispatch) -> None:
        assert (await _call(dispatch, "conjugate_verb")).startswith("Error")
