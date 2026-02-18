"""Results header component showing sentence info and script variants."""

from typing import Any, Callable

import streamlit as st

from sanskrit_analyzer.ui.styles import confidence_class


def render_results_header(
    result: dict[str, Any],
    on_compare: Callable[[], None],
) -> None:
    """Render the results header with sentence info and script variants.

    Args:
        result: The analysis result containing sentence data.
        on_compare: Callback when compare button is clicked.
    """
    sentence_data = result.get("sentence", {})
    original = sentence_data.get("original", "")
    confidence = result.get("confidence", 0)
    scripts = sentence_data.get("scripts", {})

    st.markdown('<div class="results-header">', unsafe_allow_html=True)

    # Main header row
    col_sentence, col_confidence, col_action = st.columns([3, 1, 1])

    with col_sentence:
        st.markdown(f"**Sentence:** {original}")

    with col_confidence:
        _render_confidence_badge(confidence)

    with col_action:
        if st.button("Compare Parses", key="compare_btn"):
            on_compare()

    # Script variants row
    if scripts:
        _render_script_variants(scripts)

    st.markdown("</div>", unsafe_allow_html=True)


def _render_confidence_badge(confidence: float) -> None:
    """Render a confidence badge with appropriate styling.

    Args:
        confidence: Confidence value between 0 and 1.
    """
    percentage = int(confidence * 100)
    css_class = confidence_class(confidence)

    st.markdown(
        f'<span class="confidence-badge {css_class}">'
        f"Confidence: {percentage}%</span>",
        unsafe_allow_html=True,
    )


def _render_script_variants(scripts: dict[str, str]) -> None:
    """Render the script variant display.

    Args:
        scripts: Dictionary mapping script names to text.
    """
    st.markdown('<div class="script-variants">', unsafe_allow_html=True)

    variants_html = []

    # Common script display order
    script_order = ["devanagari", "iast", "slp1", "hk", "itrans"]

    for script in script_order:
        if script in scripts:
            label = script.upper() if script != "devanagari" else "देवनागरी"
            variants_html.append(
                f'<span class="script-variant">{label}: {scripts[script]}</span>'
            )

    # Any remaining scripts not in the order
    for script, text in scripts.items():
        if script not in script_order:
            variants_html.append(
                f'<span class="script-variant">{script}: {text}</span>'
            )

    st.markdown(" ".join(variants_html), unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)
