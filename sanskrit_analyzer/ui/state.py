"""Session state management for the Streamlit UI."""

from datetime import datetime
from typing import Any

import streamlit as st

MAX_HISTORY_SIZE = 20


def init_state() -> None:
    """Initialize session state with default values."""
    if "history" not in st.session_state:
        st.session_state.history = []

    if "analysis_result" not in st.session_state:
        st.session_state.analysis_result = None

    if "selected_mode" not in st.session_state:
        st.session_state.selected_mode = "educational"

    if "show_compare" not in st.session_state:
        st.session_state.show_compare = False

    if "expanded_parses" not in st.session_state:
        st.session_state.expanded_parses = set()

    if "expanded_words" not in st.session_state:
        st.session_state.expanded_words = set()

    if "sanskrit_input" not in st.session_state:
        st.session_state.sanskrit_input = ""

    # Apply pending input (set by example/history clicks, applied before widget creation)
    if "pending_input" in st.session_state:
        st.session_state.sanskrit_input = st.session_state.pending_input
        del st.session_state.pending_input


def get_history() -> list[dict[str, Any]]:
    """Get the current history list.

    Returns:
        List of history entries as dictionaries.
    """
    init_state()
    return st.session_state.history


def add_to_history(text: str, mode: str) -> None:
    """Add a new entry to history.

    Args:
        text: The analyzed text.
        mode: The analysis mode used.
    """
    init_state()

    entry = {
        "text": text,
        "mode": mode,
        "timestamp": datetime.now().isoformat(),
    }

    # Remove duplicate if exists
    st.session_state.history = [
        h for h in st.session_state.history if h["text"] != text
    ]

    # Add to front
    st.session_state.history.insert(0, entry)

    # Enforce max size (FIFO)
    if len(st.session_state.history) > MAX_HISTORY_SIZE:
        st.session_state.history = st.session_state.history[:MAX_HISTORY_SIZE]


def clear_history() -> None:
    """Clear all history entries."""
    init_state()
    st.session_state.history = []


def set_analysis_result(result: dict[str, Any] | None) -> None:
    """Store the current analysis result.

    Args:
        result: The analysis result data or None to clear.
    """
    init_state()
    st.session_state.analysis_result = result


def get_analysis_result() -> dict[str, Any] | None:
    """Get the current analysis result.

    Returns:
        The stored analysis result or None.
    """
    init_state()
    return st.session_state.analysis_result


def _toggle_expanded(item_id: str, state_key: str) -> None:
    """Toggle expansion state of an item in a set.

    Args:
        item_id: The item identifier.
        state_key: The session state key containing the set.
    """
    init_state()
    expanded_set = getattr(st.session_state, state_key)
    if item_id in expanded_set:
        expanded_set.discard(item_id)
    else:
        expanded_set.add(item_id)


def _is_expanded(item_id: str, state_key: str) -> bool:
    """Check if an item is expanded.

    Args:
        item_id: The item identifier.
        state_key: The session state key containing the set.

    Returns:
        True if expanded, False otherwise.
    """
    init_state()
    return item_id in getattr(st.session_state, state_key)


def toggle_parse_expanded(parse_id: str) -> None:
    """Toggle expansion state of a parse."""
    _toggle_expanded(parse_id, "expanded_parses")


def is_parse_expanded(parse_id: str) -> bool:
    """Check if a parse is expanded."""
    return _is_expanded(parse_id, "expanded_parses")


def toggle_word_expanded(word_id: str) -> None:
    """Toggle expansion state of a word detail card."""
    _toggle_expanded(word_id, "expanded_words")


def is_word_expanded(word_id: str) -> bool:
    """Check if a word detail card is expanded."""
    return _is_expanded(word_id, "expanded_words")
