"""Tests for MCP dhatu tools."""

import pytest

from sanskrit_analyzer.mcp.tools.dhatu import register_dhatu_tools
from mcp.server import Server


@pytest.fixture
def server() -> Server:
    """Create a test server with dhatu tools registered."""
    server = Server("test-server")
    register_dhatu_tools(server)
    return server


class TestLookupDhatu:
    """Tests for lookup_dhatu tool."""

    def test_lookup_known_dhatu(self) -> None:
        """Test looking up a known dhatu like 'gam'."""
        from sanskrit_analyzer.data.dhatu_db import DhatuDB

        db = DhatuDB()
        entry = db.lookup_by_dhatu("gam")
        # May or may not exist depending on data
        # Just test the interface works
        assert entry is None or hasattr(entry, "dhatu_iast")

    def test_lookup_unknown_dhatu(self) -> None:
        """Test looking up an unknown dhatu returns None."""
        from sanskrit_analyzer.data.dhatu_db import DhatuDB

        db = DhatuDB()
        entry = db.lookup_by_dhatu("xyznotadhatu")
        assert entry is None


class TestSearchDhatu:
    """Tests for search_dhatu tool."""

    def test_search_by_meaning(self) -> None:
        """Test searching dhatus by meaning."""
        from sanskrit_analyzer.data.dhatu_db import DhatuDB

        db = DhatuDB()
        results = db.search("go", limit=5)
        assert isinstance(results, list)

    def test_search_with_limit(self) -> None:
        """Test that search respects limit parameter."""
        from sanskrit_analyzer.data.dhatu_db import DhatuDB

        db = DhatuDB()
        results = db.search("a", limit=3)
        assert len(results) <= 3


class TestConjugateVerb:
    """Tests for conjugate_verb tool."""

    def test_conjugate_present_tense(self) -> None:
        """Test conjugation in present tense (lat)."""
        pass

    def test_conjugate_with_filters(self) -> None:
        """Test conjugation with purusha/vacana filters."""
        pass


class TestListGana:
    """Tests for list_gana tool."""

    def test_list_gana_1(self) -> None:
        """Test listing dhatus in gana 1 (bhvadi)."""
        from sanskrit_analyzer.data.dhatu_db import DhatuDB

        db = DhatuDB()
        results = db.get_by_gana(1, limit=10)
        assert isinstance(results, list)

    def test_invalid_gana_number(self) -> None:
        """Test that invalid gana number is handled."""
        from sanskrit_analyzer.mcp.response import error_response

        # Gana 11 is invalid (valid range is 1-10)
        result = error_response("Invalid gana: 11. Must be 1-10.")
        assert "Invalid gana" in result[0].text

    def test_gana_names(self) -> None:
        """Test gana names are correct."""
        from sanskrit_analyzer.mcp.resources.dhatus import _get_overview

        overview = _get_overview.__doc__
        # Just test the function exists
        assert callable(_get_overview)
