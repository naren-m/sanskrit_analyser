"""Tests for the Sanskrit Analyzer UI styles module."""

from sanskrit_analyzer.ui.styles import confidence_class, expand_icon
from tests._cases import check_cases

CASES = [
    # confidence_class bands: >=0.8 high, >=0.5 medium, else low.
    ("1.0 is high", confidence_class, 1.0, "confidence-high"),
    ("0.95 is high", confidence_class, 0.95, "confidence-high"),
    ("0.94 top-parse confidence is high", confidence_class, 0.94, "confidence-high"),
    ("0.80 boundary is high", confidence_class, 0.80, "confidence-high"),
    ("0.79 is medium", confidence_class, 0.79, "confidence-medium"),
    ("0.65 is medium", confidence_class, 0.65, "confidence-medium"),
    ("0.50 boundary is medium", confidence_class, 0.50, "confidence-medium"),
    ("0.49 is low", confidence_class, 0.49, "confidence-low"),
    ("0.30 is low", confidence_class, 0.30, "confidence-low"),
    ("0.10 is low", confidence_class, 0.10, "confidence-low"),
    ("0.0 is low", confidence_class, 0.0, "confidence-low"),
    # expand_icon: expanded shows a down arrow, collapsed a right arrow.
    ("expanded shows down arrow", expand_icon, True, "▼"),
    ("collapsed shows right arrow", expand_icon, False, "▸"),
]


def test_style_helpers() -> None:
    def check(fn, arg, expected):
        got = fn(arg)
        assert got == expected, f"{fn.__name__}({arg!r}) = {got!r}, want {expected!r}"

    check_cases(CASES, check)
