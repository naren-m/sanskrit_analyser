"""Tests for the Sanskrit Analyzer UI session state management.

Each row starts from a fresh session state, applies ``setup`` attributes,
runs ``action`` against the state module, and checks the return value and the
resulting state. ``history`` is compared as ``(text, mode)`` pairs because
timestamps are wall-clock.
"""

from typing import Any
from unittest.mock import MagicMock

from sanskrit_analyzer.ui import state as S  # noqa: N812
from tests._cases import check_cases
from tests.ui.conftest import MockSessionState

_UNSET = object()
DELETE = object()


def _history(n: int) -> list[dict[str, str]]:
    return [{"text": f"entry{i}", "mode": "quick", "timestamp": "t"} for i in range(n)]


def _toggle_twice(toggle, is_expanded, item_id):
    toggle(item_id)
    first = is_expanded(item_id)
    toggle(item_id)
    return (first, is_expanded(item_id))


HISTORY_CASES = [
    (
        "init_state restores a missing history key",
        {"history": DELETE},
        S.init_state,
        _UNSET,
        {"history": []},
    ),
    (
        "get_history returns the stored list",
        {"history": [{"text": "test", "mode": "quick"}]},
        S.get_history,
        [{"text": "test", "mode": "quick"}],
        {},
    ),
    (
        "add_to_history puts text and mode on the list",
        {},
        lambda: S.add_to_history("रामः गच्छति", "educational"),
        _UNSET,
        {"history": [("रामः गच्छति", "educational")]},
    ),
    (
        "add_to_history replaces a duplicate text with the new mode",
        {"history": [{"text": "test", "mode": "quick", "timestamp": "old"}]},
        lambda: S.add_to_history("test", "educational"),
        _UNSET,
        {"history": [("test", "educational")]},
    ),
    (
        "add_to_history drops the oldest entry past MAX_HISTORY_SIZE",
        {"history": _history(S.MAX_HISTORY_SIZE)},
        lambda: S.add_to_history("new entry", "educational"),
        _UNSET,
        {
            "history": [("new entry", "educational")]
            + [(f"entry{i}", "quick") for i in range(S.MAX_HISTORY_SIZE - 1)]
        },
    ),
    (
        "clear_history empties the list",
        {"history": [{"text": "test"}]},
        S.clear_history,
        _UNSET,
        {"history": []},
    ),
]

RESULT_CASES = [
    (
        "set_analysis_result stores the result",
        {},
        lambda: S.set_analysis_result({"parses": []}),
        _UNSET,
        {"analysis_result": {"parses": []}},
    ),
    (
        "set_analysis_result(None) clears the result",
        {"analysis_result": {"old": "data"}},
        lambda: S.set_analysis_result(None),
        _UNSET,
        {"analysis_result": None},
    ),
    (
        "get_analysis_result returns the stored result",
        {"analysis_result": {"parses": []}},
        S.get_analysis_result,
        {"parses": []},
        {},
    ),
    (
        "selected parse id starts None and round-trips",
        {},
        lambda: (
            S.get_selected_parse_id(),
            S.set_selected_parse_id("parse_2"),
            S.get_selected_parse_id(),
        )[::2],
        (None, "parse_2"),
        {},
    ),
    (
        "a fresh analysis result clears the previous parse selection",
        {},
        lambda: (
            S.set_selected_parse_id("parse_2"),
            S.set_analysis_result({"parses": []}),
            S.get_selected_parse_id(),
        )[2],
        None,
        {},
    ),
]

EXPANSION_CASES = [
    (
        "toggle_parse_expanded adds a missing id",
        {"expanded_parses": set()},
        lambda: S.toggle_parse_expanded("parse_1"),
        _UNSET,
        {"expanded_parses": {"parse_1"}},
    ),
    (
        "toggle_parse_expanded removes a present id",
        {"expanded_parses": {"parse_1"}},
        lambda: S.toggle_parse_expanded("parse_1"),
        _UNSET,
        {"expanded_parses": set()},
    ),
    (
        "is_parse_expanded true when present",
        {"expanded_parses": {"parse_1"}},
        lambda: S.is_parse_expanded("parse_1"),
        True,
        {},
    ),
    (
        "is_parse_expanded false when absent",
        {"expanded_parses": set()},
        lambda: S.is_parse_expanded("parse_1"),
        False,
        {},
    ),
    (
        "toggle_word_expanded adds a missing id",
        {"expanded_words": set()},
        lambda: S.toggle_word_expanded("word_1"),
        _UNSET,
        {"expanded_words": {"word_1"}},
    ),
    (
        "toggle_word_expanded removes a present id",
        {"expanded_words": {"word_1"}},
        lambda: S.toggle_word_expanded("word_1"),
        _UNSET,
        {"expanded_words": set()},
    ),
    (
        "is_word_expanded true when present",
        {"expanded_words": {"word_1"}},
        lambda: S.is_word_expanded("word_1"),
        True,
        {},
    ),
    (
        "is_word_expanded false when absent",
        {"expanded_words": set()},
        lambda: S.is_word_expanded("word_1"),
        False,
        {},
    ),
    (
        "parse toggle round-trips expanded then collapsed",
        {},
        lambda: _toggle_twice(S.toggle_parse_expanded, S.is_parse_expanded, "parse_1"),
        (True, False),
        {},
    ),
    (
        "word toggle round-trips expanded then collapsed",
        {},
        lambda: _toggle_twice(S.toggle_word_expanded, S.is_word_expanded, "word_1"),
        (True, False),
        {},
    ),
]


def _checker(mock_streamlit: MagicMock):
    def check(setup: dict[str, Any], action, returns, expected: dict[str, Any]) -> None:
        state = MockSessionState()
        for key, value in setup.items():
            if value is DELETE:
                delattr(state, key)
            else:
                setattr(state, key, value)
        mock_streamlit.session_state = state

        got = action()
        if returns is not _UNSET:
            assert got == returns, f"returned {got!r}, want {returns!r}"
        for key, want in expected.items():
            have = getattr(state, key)
            if key == "history" and want:
                have = [(h["text"], h["mode"]) for h in have]
            assert have == want, f"{key} = {have!r}, want {want!r}"

    return check


def test_history(mock_streamlit: MagicMock) -> None:
    check_cases(HISTORY_CASES, _checker(mock_streamlit))


def test_analysis_result_and_selection(mock_streamlit: MagicMock) -> None:
    check_cases(RESULT_CASES, _checker(mock_streamlit))


def test_expansion_toggles(mock_streamlit: MagicMock) -> None:
    check_cases(EXPANSION_CASES, _checker(mock_streamlit))
