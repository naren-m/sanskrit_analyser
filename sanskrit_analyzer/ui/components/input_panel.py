"""Input panel component with text input, examples, and history."""

from typing import Callable

import streamlit as st

from sanskrit_analyzer.ui.state import get_history

# Sample Sanskrit sentences for quick testing
EXAMPLES = [
    "रामः गच्छति",
    "अहं पठामि",
    "सः पुस्तकं पठति",
    "वने मृगाः चरन्ति",
    "बालकः फलं खादति",
]

MODES = {
    "educational": "Educational - Detailed explanations",
    "research": "Research - Full analysis",
    "quick": "Quick - Essential info only",
}


def render_input_panel(
    on_analyze: Callable[[str, str], None],
    on_example_click: Callable[[str], None],
) -> None:
    """Render the input panel with text area, examples, and history.

    Args:
        on_analyze: Callback when analyze button is clicked. Takes (text, mode).
        on_example_click: Callback when an example/history item is clicked.
    """
    col_input, col_sidebar = st.columns([2, 1])

    with col_input:
        _render_text_input(on_analyze)

    with col_sidebar:
        _render_examples(on_example_click)
        _render_history(on_example_click)


def _render_text_input(on_analyze: Callable[[str, str], None]) -> None:
    """Render the main text input area."""
    st.markdown("**Enter Sanskrit text:**")

    text = st.text_area(
        label="Sanskrit text",
        height=100,
        placeholder="Enter Sanskrit text here...",
        key="sanskrit_input",
        label_visibility="collapsed",
    )

    col_btn, col_mode = st.columns([1, 2])

    with col_mode:
        mode = st.selectbox(
            "Mode",
            options=list(MODES.keys()),
            format_func=lambda x: MODES[x],
            key="mode_select",
            label_visibility="collapsed",
        )

    with col_btn:
        if st.button("Analyze", type="primary", use_container_width=True):
            if text and text.strip():
                on_analyze(text.strip(), mode)
            else:
                st.warning("Please enter some text to analyze.")


def _render_examples(on_click: Callable[[str], None]) -> None:
    """Render the examples section."""
    st.markdown("**Examples:**")

    for example in EXAMPLES:
        if st.button(
            example,
            key=f"example_{example}",
            use_container_width=True,
        ):
            on_click(example)


def _render_history(on_click: Callable[[str], None]) -> None:
    """Render the history section."""
    history = get_history()

    if not history:
        return

    st.markdown("---")
    st.markdown("**History:**")

    for i, entry in enumerate(history[:10]):  # Show last 10
        text = entry["text"]
        display_text = text if len(text) <= 30 else f"{text[:27]}..."

        if st.button(
            display_text,
            key=f"history_{i}",
            use_container_width=True,
        ):
            on_click(text)
