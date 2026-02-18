"""Main Streamlit application for the Sanskrit Analyzer UI."""

import asyncio

import streamlit as st

from sanskrit_analyzer.ui.api_client import SanskritAPIClient
from sanskrit_analyzer.ui.components.diff_view import render_diff_view
from sanskrit_analyzer.ui.components.input_panel import render_input_panel
from sanskrit_analyzer.ui.components.parse_tree import render_parse_list
from sanskrit_analyzer.ui.components.results_header import render_results_header
from sanskrit_analyzer.ui.state import (
    add_to_history,
    get_analysis_result,
    init_state,
    set_analysis_result,
)
from sanskrit_analyzer.ui.styles import inject_css

# Page configuration
st.set_page_config(
    page_title="Sanskrit Analyzer",
    page_icon="📜",
    layout="wide",
)


def main() -> None:
    """Main application entry point."""
    # Initialize state (includes pending_input handling) and styles
    init_state()
    inject_css()

    # Header
    st.title("Sanskrit Analyzer")

    # Input panel
    render_input_panel(
        on_analyze=handle_analyze,
        on_example_click=handle_example_click,
    )

    # Results area
    result = get_analysis_result()

    if result:
        st.markdown("---")
        _render_results(result)


def handle_analyze(text: str, mode: str) -> None:
    """Handle the analyze button click.

    Args:
        text: Sanskrit text to analyze.
        mode: Analysis mode.
    """
    with st.spinner("Analyzing..."):
        client = SanskritAPIClient()
        result = asyncio.run(client.analyze(text, mode))

    if result.success and result.data:
        set_analysis_result(result.data)
        add_to_history(text, mode)
        st.rerun()
    elif result.error:
        st.error(result.error.message)
        if result.error.details:
            with st.expander("Details"):
                st.code(result.error.details)


def handle_example_click(text: str) -> None:
    """Handle clicking on an example or history item.

    Args:
        text: The text to load into the input.
    """
    # Use pending_input to avoid modifying widget state after instantiation
    st.session_state.pending_input = text
    st.rerun()


def _render_results(result: dict) -> None:
    """Render the results area.

    Args:
        result: The analysis result data.
    """
    # Check if compare mode is active
    if st.session_state.get("show_compare", False):
        parses = result.get("parses", [])
        render_diff_view(
            parses=parses,
            on_close=_close_compare,
        )
        return

    # Results header
    render_results_header(
        result=result,
        on_compare=_open_compare,
    )

    # Parse tree
    parses = result.get("parses", [])
    if parses:
        selected_id = parses[0].get("parse_id")
        render_parse_list(
            parses=parses,
            selected_parse_id=selected_id,
            on_select=_handle_parse_select,
        )
    else:
        st.warning("No parse candidates found.")


def _open_compare() -> None:
    """Open the compare view."""
    st.session_state.show_compare = True
    st.rerun()


def _close_compare() -> None:
    """Close the compare view."""
    st.session_state.show_compare = False
    st.rerun()


def _handle_parse_select(parse_id: str) -> None:
    """Handle selecting a different parse.

    Args:
        parse_id: The selected parse ID.
    """
    # For now, just reorder to put selected first
    result = get_analysis_result()
    if result:
        parses = result.get("parses", [])
        for i, p in enumerate(parses):
            if p.get("parse_id") == parse_id:
                # Move to front
                parses.insert(0, parses.pop(i))
                break
        st.rerun()


if __name__ == "__main__":
    main()
