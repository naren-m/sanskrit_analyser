"""Tests for transliteration utilities."""

from sanskrit_analyzer.models.scripts import Script
from sanskrit_analyzer.utils.transliterate import (
    to_devanagari,
    to_iast,
    to_slp1,
    transliterate,
)
from tests._cases import check_cases

D, I, S = Script.DEVANAGARI, Script.IAST, Script.SLP1  # noqa: E741

# (id, text, source, target, expected)
TRANSLITERATE_CASES = [
    ("deva_to_iast", "राम", D, I, "rāma"),
    ("deva_to_slp1", "राम", D, S, "rAma"),
    ("iast_to_deva", "rāma", I, D, "राम"),
    ("iast_to_slp1", "rāma", I, S, "rAma"),
    ("slp1_to_deva", "rAma", S, D, "राम"),
    ("slp1_to_iast", "rAma", S, I, "rāma"),
    ("same_script_returns_input", "राम", D, D, "राम"),
    ("empty_returns_empty", "", D, I, ""),
    ("whitespace_only_returns_input", "   ", D, I, "   "),
]


def test_transliterate() -> None:
    def check(text, source, target, expected):
        assert transliterate(text, source, target) == expected

    check_cases(TRANSLITERATE_CASES, check)

    # योगश्चित्तवृत्तिनिरोधः (Yoga Sutra 1.2) survives as a whole sentence.
    iast = transliterate("योगश्चित्तवृत्तिनिरोधः", D, I).lower()
    assert "yoga" in iast
    assert "nirodha" in iast


# (id, convenience function, text, source, expected)
CONVENIENCE_CASES = [
    ("to_slp1_from_deva", to_slp1, "राम", D, "rAma"),
    ("to_slp1_from_iast", to_slp1, "rāma", I, "rAma"),
    ("to_deva_from_slp1", to_devanagari, "rAma", S, "राम"),
    ("to_deva_from_iast", to_devanagari, "rāma", I, "राम"),
    ("to_iast_from_slp1", to_iast, "rAma", S, "rāma"),
    ("to_iast_from_deva", to_iast, "राम", D, "rāma"),
]


def test_convenience_functions() -> None:
    def check(fn, text, source, expected):
        assert fn(text, source) == expected

    check_cases(CONVENIENCE_CASES, check)
