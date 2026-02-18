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


def toggle_parse_expanded(parse_id: str) -> None:
    """Toggle expansion state of a parse.

    Args:
        parse_id: The parse identifier.
    """
    init_state()
    if parse_id in st.session_state.expanded_parses:
        st.session_state.expanded_parses.discard(parse_id)
    else:
        st.session_state.expanded_parses.add(parse_id)


def is_parse_expanded(parse_id: str) -> bool:
    """Check if a parse is expanded.

    Args:
        parse_id: The parse identifier.

    Returns:
        True if expanded, False otherwise.
    """
    init_state()
    return parse_id in st.session_state.expanded_parses


def toggle_word_expanded(word_id: str) -> None:
    """Toggle expansion state of a word detail card.

    Args:
        word_id: The word identifier.
    """
    init_state()
    if word_id in st.session_state.expanded_words:
        st.session_state.expanded_words.discard(word_id)
    else:
        st.session_state.expanded_words.add(word_id)


def is_word_expanded(word_id: str) -> bool:
    """Check if a word detail card is expanded.

    Args:
        word_id: The word identifier.

    Returns:
        True if expanded, False otherwise.
    """
    init_state()
    return word_id in st.session_state.expanded_words
