"""Tests for the Sanskrit Analyzer UI styles module."""

import pytest

from sanskrit_analyzer.ui.styles import confidence_class, expand_icon


class TestConfidenceClass:
    """Tests for confidence_class function."""

    def test_high_confidence(self) -> None:
        """High confidence (>=80%) returns high class."""
        assert confidence_class(0.95) == "confidence-high"
        assert confidence_class(0.80) == "confidence-high"

    def test_medium_confidence(self) -> None:
        """Medium confidence (50-79%) returns medium class."""
        assert confidence_class(0.79) == "confidence-medium"
        assert confidence_class(0.50) == "confidence-medium"

    def test_low_confidence(self) -> None:
        """Low confidence (<50%) returns low class."""
        assert confidence_class(0.49) == "confidence-low"
        assert confidence_class(0.10) == "confidence-low"
        assert confidence_class(0.0) == "confidence-low"

    def test_edge_cases(self) -> None:
        """Edge cases at boundaries."""
        assert confidence_class(1.0) == "confidence-high"
        assert confidence_class(0.8) == "confidence-high"
        assert confidence_class(0.5) == "confidence-medium"


class TestExpandIcon:
    """Tests for expand_icon function."""

    def test_expanded_returns_down_arrow(self) -> None:
        """Expanded state shows down arrow."""
        assert expand_icon(True) == "▼"

    def test_collapsed_returns_right_arrow(self) -> None:
        """Collapsed state shows right arrow."""
        assert expand_icon(False) == "▸"
