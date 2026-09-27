"""Tests for the word card component helpers."""

from unittest.mock import patch

from sanskrit_analyzer.ui.components.word_card import (
    _meaning_to_str,
    _render_confidence_footer,
    _render_meanings_section,
)
from tests._cases import check_cases

MEANING_CASES = [
    ("plain string passes through", "goes", "goes"),
    ("dict uses its text field", {"text": "to go"}, "to go"),
    ("dict falls back to meaning field", {"meaning": "pleasing"}, "pleasing"),
    ("dict without a known key is empty", {}, ""),
]

# (id, renderer, arg, substrings that must appear, substrings that must not)
RENDER_CASES = [
    (
        "dict-shaped meanings render as strings instead of raising",
        _render_meanings_section,
        [{"text": "to go"}, "pleasing"],
        ["to go", "pleasing"],
        [],
    ),
    (
        "HTML in backend meanings is escaped, not interpolated raw",
        _render_meanings_section,
        ["<script>alert(1)</script>"],
        ["&lt;script&gt;"],
        ["<script>alert(1)</script>"],
    ),
    (
        "None confidence renders as 0% instead of raising TypeError",
        _render_confidence_footer,
        None,
        ["0%"],
        [],
    ),
]


def test_meaning_to_str() -> None:
    def check(meaning, expected):
        assert _meaning_to_str(meaning) == expected

    check_cases(MEANING_CASES, check)


def test_render_sections() -> None:
    def check(render, arg, present, absent):
        with patch("sanskrit_analyzer.ui.components.word_card.st") as mock_st:
            render(arg)
            rendered = mock_st.markdown.call_args[0][0]
        for s in present:
            assert s in rendered, f"{s!r} missing from {rendered!r}"
        for s in absent:
            assert s not in rendered, f"{s!r} leaked into {rendered!r}"

    check_cases(RENDER_CASES, check)
