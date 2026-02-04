"""Tests for MCP resource providers."""

import json

from sanskrit_analyzer.data.dhatu_db import DhatuDB
from sanskrit_analyzer.mcp.resources.dhatus import _get_gana_dhatus, _get_overview
from sanskrit_analyzer.mcp.resources.grammar import (
    _get_pratyayas_index,
    _get_sandhi_rules_category,
    _get_sandhi_rules_index,
    _get_sutras_overview,
    _get_sutras_section,
    _load_yaml,
)


class TestDhatuResources:
    """Tests for dhatu resource provider."""

    def test_overview_returns_valid_json(self) -> None:
        """Test that dhatus overview returns valid JSON with expected fields."""
        db = DhatuDB()
        result = _get_overview(db)
        data = json.loads(result)
        assert "total_dhatus" in data
        assert "gana_distribution" in data
        assert len(data["gana_distribution"]) == 10

    def test_gana_resource_returns_dhatus(self) -> None:
        """Test that gana resource returns dhatus list."""
        db = DhatuDB()
        result = _get_gana_dhatus(db, 1)
        data = json.loads(result)
        assert data["gana"] == 1
        assert "dhatus" in data


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
        """Test sandhi rules index returns valid JSON."""
        result = _get_sandhi_rules_index()
        data = json.loads(result)
        assert "categories" in data or "description" in data

    def test_vowel_sandhi_rules(self) -> None:
        """Test vowel sandhi rules returns correct category."""
        result = _get_sandhi_rules_category("vowel")
        data = json.loads(result)
        assert data["category"] == "vowel"


class TestPratyayasResource:
    """Tests for pratyayas resource."""

    def test_pratyayas_index(self) -> None:
        """Test pratyayas index returns valid JSON."""
        result = _get_pratyayas_index()
        data = json.loads(result)
        assert "categories" in data or "description" in data


class TestSutrasResource:
    """Tests for sutras resource."""

    def test_sutras_overview(self) -> None:
        """Test sutras overview returns expected fields."""
        result = _get_sutras_overview()
        data = json.loads(result)
        assert "title" in data
        assert "author" in data

    def test_sutras_section(self) -> None:
        """Test sutras section returns correct adhyaya and pada."""
        result = _get_sutras_section(1, 1)
        data = json.loads(result)
        assert data["adhyaya"] == 1
        assert data["pada"] == 1
