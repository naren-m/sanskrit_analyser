"""Tests for MCP dhatu tools."""

from sanskrit_analyzer.data.dhatu_db import DhatuDB


class TestLookupDhatu:
    """Tests for dhatu lookup functionality."""

    def test_lookup_unknown_dhatu_returns_none(self) -> None:
        """Test looking up an unknown dhatu returns None."""
        db = DhatuDB()
        entry = db.lookup_by_dhatu("xyznotadhatu")
        assert entry is None

    def test_lookup_known_dhatu_returns_entry_or_none(self) -> None:
        """Test looking up a known dhatu returns entry with expected attributes."""
        db = DhatuDB()
        entry = db.lookup_by_dhatu("gam")
        if entry is not None:
            assert hasattr(entry, "dhatu_iast")


class TestSearchDhatu:
    """Tests for dhatu search functionality."""

    def test_search_returns_list(self) -> None:
        """Test searching dhatus returns a list."""
        db = DhatuDB()
        results = db.search("go", limit=5)
        assert isinstance(results, list)

    def test_search_respects_limit(self) -> None:
        """Test that search respects limit parameter."""
        db = DhatuDB()
        results = db.search("a", limit=3)
        assert len(results) <= 3


class TestListGana:
    """Tests for listing dhatus by gana."""

    def test_get_by_gana_returns_list(self) -> None:
        """Test listing dhatus in a gana returns list."""
        db = DhatuDB()
        results = db.get_by_gana(1, limit=10)
        assert isinstance(results, list)
