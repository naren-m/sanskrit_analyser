"""Tests for the diff view component logic."""

from unittest.mock import patch

from sanskrit_analyzer.ui.components.diff_view import (
    _compare_words,
    _compute_differences,
    _flatten_words,
    _render_parse_column,
    render_diff_view,
)
from tests._cases import check_cases

RAMA = {"lemma": "rama", "scripts": {"devanagari": "राम"}, "morphology": {"pos": "noun"}}
SITA = {"lemma": "sita", "scripts": {"devanagari": "सीता"}, "morphology": {"pos": "noun"}}


def _parse(*groups):
    return {"sandhi_groups": [{"base_words": list(words)} for words in groups]}


# (id, parse, substrings that must appear, substrings that must not)
RENDER_COLUMN_CASES = [
    (
        "None parse confidence renders as 0% instead of raising",
        {"confidence": None, "sandhi_groups": []},
        ["0%"],
        [],
    ),
    (
        "HTML in backend surface/word data is escaped",
        {
            "confidence": 0.5,
            "sandhi_groups": [
                {
                    "surface_form": "<b>x</b>",
                    "scripts": {"devanagari": "<b>x</b>"},
                    "base_words": [{"lemma": "<i>w</i>", "scripts": {"devanagari": "<i>w</i>"}}],
                }
            ],
        },
        ["&lt;b&gt;x&lt;/b&gt;"],
        ["<b>x</b>"],
    ),
]

# (id, left, right, substring expected in some diff line; None = no diffs)
DIFF_CASES = [
    ("identical parses have no differences", _parse([RAMA]), _parse([RAMA]), None),
    (
        "different word count is reported",
        _parse([{"lemma": "a"}, {"lemma": "b"}]),
        _parse([{"lemma": "a"}]),
        "Word count",
    ),
    (
        "different sandhi group count is reported",
        _parse([{"lemma": "a"}], [{"lemma": "b"}]),
        _parse([{"lemma": "a"}, {"lemma": "b"}]),
        "Sandhi groups",
    ),
    (
        "different lemmas are reported",
        _parse([{"lemma": "rama", "scripts": {"devanagari": "राम"}}]),
        _parse([{"lemma": "lakshmana", "scripts": {"devanagari": "लक्ष्मण"}}]),
        "Different lemma",
    ),
    (
        "different lemmas with morphology are reported",
        _parse([RAMA]),
        _parse([SITA]),
        "Different lemma",
    ),
]

FLATTEN_CASES = [
    ("empty groups flatten to nothing", [], []),
    (
        "single group yields its words",
        [{"base_words": [{"lemma": "a"}, {"lemma": "b"}]}],
        ["a", "b"],
    ),
    (
        "multiple groups flatten in order",
        [{"base_words": [{"lemma": "a"}]}, {"base_words": [{"lemma": "b"}, {"lemma": "c"}]}],
        ["a", "b", "c"],
    ),
]

# (id, left, right, position, substring expected; None = words match)
COMPARE_CASES = [
    ("identical words compare equal", RAMA, RAMA, 1, None),
    ("different lemmas are reported", RAMA, SITA, 1, "Different lemma"),
    (
        "same lemma with different morphology is reported",
        {**RAMA, "morphology": {"pos": "noun", "case": "nominative"}},
        {**RAMA, "morphology": {"pos": "noun", "case": "accusative"}},
        2,
        "Different analysis",
    ),
]


def test_render_parse_column() -> None:
    def check(parse, present, absent):
        with patch("sanskrit_analyzer.ui.components.diff_view.st") as mock_st:
            _render_parse_column(parse)
            rendered = mock_st.markdown.call_args[0][0]
        for s in present:
            assert s in rendered, f"{s!r} missing from {rendered!r}"
        for s in absent:
            assert s not in rendered, f"{s!r} leaked into {rendered!r}"

    check_cases(RENDER_COLUMN_CASES, check)


def test_render_diff_view_none_confidence_in_options() -> None:
    """None confidence in the compare selectboxes renders as 0% without raising."""
    parses = [
        {"confidence": None, "sandhi_groups": []},
        {"confidence": None, "sandhi_groups": []},
    ]
    with patch("sanskrit_analyzer.ui.components.diff_view.st") as mock_st:
        mock_st.button.return_value = False
        mock_st.columns.return_value = (mock_st, mock_st)
        mock_st.selectbox.side_effect = ["Parse 1 (0%)", "Parse 2 (0%)"]
        # Should not raise a TypeError building the options dict.
        render_diff_view(parses, on_close=lambda: None)


def test_compute_differences() -> None:
    def check(left, right, expected):
        diffs = _compute_differences(left, right)
        if expected is None:
            assert diffs == []
        else:
            assert any(expected in d for d in diffs), diffs

    check_cases(DIFF_CASES, check)


def test_flatten_words() -> None:
    def check(groups, lemmas):
        assert [w["lemma"] for w in _flatten_words(groups)] == lemmas

    check_cases(FLATTEN_CASES, check)


def test_compare_words() -> None:
    def check(left, right, position, expected):
        diff = _compare_words(left, right, position)
        if expected is None:
            assert diff is None
        else:
            assert diff is not None and expected in diff, diff

    check_cases(COMPARE_CASES, check)
