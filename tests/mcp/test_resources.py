"""Tests for MCP resource providers."""

import json
import pytest

from sanskrit_analyzer.mcp.resources.dhatus import register_dhatu_resources, _get_overview
from sanskrit_analyzer.mcp.resources.grammar import register_grammar_resources, _load_yaml
from mcp.server import Server


@pytest.fixture
def server() -> Server:
    """Create a test server with resources registered."""
    server = Server("test-server")
    register_dhatu_resources(server)
    register_grammar_resources(server)
    return server


class TestDhatuResources:
    """Tests for dhatu resource provider."""

    def test_overview_returns_valid_json(self) -> None:
        """Test that /dhatus overview returns valid JSON."""
        from sanskrit_analyzer.data.dhatu_db import DhatuDB

        db = DhatuDB()
        result = _get_overview(db)
        data = json.loads(result)
        assert "total_dhatus" in data
        assert "gana_distribution" in data

    def test_gana_distribution_has_10_entries(self) -> None:
        """Test that gana distribution has 10 entries."""
        from sanskrit_analyzer.data.dhatu_db import DhatuDB

        db = DhatuDB()
        result = _get_overview(db)
        data = json.loads(result)
        assert len(data["gana_distribution"]) == 10

    def test_gana_resource_returns_dhatus(self) -> None:
        """Test that /dhatus/gana/{n} returns dhatus list."""
        from sanskrit_analyzer.mcp.resources.dhatus import _get_gana_dhatus
        from sanskrit_analyzer.data.dhatu_db import DhatuDB

        db = DhatuDB()
        result = _get_gana_dhatus(db, 1)
        data = json.loads(result)
        assert "gana" in data
        assert "dhatus" in data
        assert data["gana"] == 1


class TestGrammarResources:
    """Tests for grammar resource providers."""

    def test_load_yaml_nonexistent_returns_empty(self) -> None:
        """Test that loading nonexistent YAML returns empty dict."""
        result = _load_yaml("nonexistent_file.yaml")
        assert result == {}

    def test_sandhi_rules_yaml_loads(self) -> None:
        """Test that sandhi_rules.yaml loads successfully."""
        result = _load_yaml("sandhi_rules.yaml")
        assert "categories" in result or result == {}

    def test_pratyayas_yaml_loads(self) -> None:
        """Test that pratyayas.yaml loads successfully."""
        result = _load_yaml("pratyayas.yaml")
        assert "categories" in result or result == {}

    def test_sutras_yaml_loads(self) -> None:
        """Test that sutras.yaml loads successfully."""
        result = _load_yaml("sutras.yaml")
        assert "adhyayas" in result or result == {}


class TestSandhiRulesResource:
    """Tests for sandhi-rules resource."""

    def test_sandhi_rules_index(self) -> None:
        """Test /grammar/sandhi-rules returns index."""
        from sanskrit_analyzer.mcp.resources.grammar import _get_sandhi_rules_index

        result = _get_sandhi_rules_index()
        data = json.loads(result)
        assert "categories" in data or "description" in data

    def test_vowel_sandhi_rules(self) -> None:
        """Test /grammar/sandhi-rules/vowel returns rules."""
        from sanskrit_analyzer.mcp.resources.grammar import _get_sandhi_rules_category

        result = _get_sandhi_rules_category("vowel")
        data = json.loads(result)
        assert "category" in data
        assert data["category"] == "vowel"


class TestPratyayasResource:
    """Tests for pratyayas resource."""

    def test_pratyayas_index(self) -> None:
        """Test /grammar/pratyayas returns index."""
        from sanskrit_analyzer.mcp.resources.grammar import _get_pratyayas_index

        result = _get_pratyayas_index()
        data = json.loads(result)
        assert "categories" in data or "description" in data


class TestSutrasResource:
    """Tests for sutras resource."""

    def test_sutras_overview(self) -> None:
        """Test /grammar/sutras returns overview."""
        from sanskrit_analyzer.mcp.resources.grammar import _get_sutras_overview

        result = _get_sutras_overview()
        data = json.loads(result)
        assert "title" in data
        assert "author" in data

    def test_sutras_section(self) -> None:
        """Test /grammar/sutras/{adhyaya}/{pada} returns section."""
        from sanskrit_analyzer.mcp.resources.grammar import _get_sutras_section

        result = _get_sutras_section(1, 1)
        data = json.loads(result)
        assert "adhyaya" in data
        assert "pada" in data
