"""Parse tree component with folder-style expansion."""

from typing import Any, Callable

import streamlit as st

from sanskrit_analyzer.ui.components.word_card import render_word_card
from sanskrit_analyzer.ui.state import is_parse_expanded, toggle_parse_expanded
from sanskrit_analyzer.ui.styles import confidence_class, expand_icon


def render_parse_list(
    parses: list[dict[str, Any]],
    selected_parse_id: str | None = None,
    on_select: Callable[[str], None] | None = None,
) -> None:
    """Render the list of parse candidates.

    Args:
        parses: List of parse tree dictionaries.
        selected_parse_id: ID of the currently selected parse.
        on_select: Callback when a parse is selected.
    """
    st.markdown("**Parse Candidates** (ranked by confidence):")

    for i, parse in enumerate(parses):
        parse_id = parse.get("parse_id", f"parse_{i}")
        confidence = parse.get("confidence", 0)
        is_selected = parse_id == selected_parse_id

        _render_parse_row(
            parse=parse,
            parse_id=parse_id,
            index=i + 1,
            confidence=confidence,
            is_selected=is_selected,
            on_select=on_select,
        )


def _render_parse_row(
    parse: dict[str, Any],
    parse_id: str,
    index: int,
    confidence: float,
    is_selected: bool,
    on_select: Callable[[str], None] | None,
) -> None:
    """Render a single parse candidate row.

    Args:
        parse: Parse tree data.
        parse_id: Unique identifier.
        index: Display index (1-based).
        confidence: Confidence value.
        is_selected: Whether this parse is selected.
        on_select: Selection callback.
    """
    is_expanded = is_parse_expanded(parse_id)

    # Row container styling
    row_class = "parse-row parse-row-selected" if is_selected else "parse-row"
    st.markdown(f'<div class="{row_class}">', unsafe_allow_html=True)

    # Header row
    col_toggle, col_label, col_preview, col_select = st.columns([0.5, 2, 3, 1])

    with col_toggle:
        icon = expand_icon(is_expanded)
        if st.button(icon, key=f"toggle_parse_{parse_id}"):
            toggle_parse_expanded(parse_id)
            st.rerun()

    with col_label:
        percentage = int(confidence * 100)
        css_class = confidence_class(confidence)
        st.markdown(
            f'Parse {index} <span class="confidence-badge {css_class}">{percentage}%</span>',
            unsafe_allow_html=True,
        )

    with col_preview:
        # Show preview of sandhi groups
        preview = _get_parse_preview(parse)
        st.markdown(f"*{preview}*")

    with col_select:
        if is_selected:
            st.markdown("✓ Selected")
        elif on_select:
            if st.button("Select", key=f"select_{parse_id}"):
                on_select(parse_id)

    # Expanded content
    if is_expanded:
        _render_parse_content(parse, parse_id)

    st.markdown("</div>", unsafe_allow_html=True)


def _get_parse_preview(parse: dict[str, Any]) -> str:
    """Generate a brief preview of the parse.

    Args:
        parse: Parse tree data.

    Returns:
        Preview string showing the sandhi groups.
    """
    sandhi_groups = parse.get("sandhi_groups", [])
    parts = []

    for sg in sandhi_groups:
        scripts = sg.get("scripts", {})
        surface = scripts.get("devanagari", sg.get("surface_form", ""))

        # Show the base words
        base_words = sg.get("base_words", [])
        if len(base_words) > 1:
            word_parts = []
            for w in base_words:
                ws = w.get("scripts", {})
                word_parts.append(ws.get("devanagari", w.get("lemma", "")))
            parts.append(f"{surface} → {' + '.join(word_parts)}")
        else:
            parts.append(surface)

    return " • ".join(parts) if parts else "—"


def _render_parse_content(parse: dict[str, Any], parse_id: str) -> None:
    """Render the expanded parse tree content.

    Args:
        parse: Parse tree data.
        parse_id: Unique identifier for generating child keys.
    """
    sandhi_groups = parse.get("sandhi_groups", [])

    for sg_idx, sg in enumerate(sandhi_groups):
        _render_sandhi_group(sg, f"{parse_id}_sg{sg_idx}")

    # Engine votes footer
    engine_votes = parse.get("engine_votes", {})
    if engine_votes:
        _render_engine_votes(engine_votes)


def _render_sandhi_group(group: dict[str, Any], group_id: str) -> None:
    """Render a sandhi group with its base words.

    Args:
        group: Sandhi group data.
        group_id: Unique identifier for generating child keys.
    """
    scripts = group.get("scripts", {})
    surface = scripts.get("devanagari", group.get("surface_form", ""))
    base_words = group.get("base_words", [])

    # Group header with type info
    sandhi_type = group.get("sandhi_type")
    compound_info = ""
    if group.get("is_compound"):
        compound_type = group.get("compound_type", "compound")
        compound_info = f" [{compound_type}]"

    type_info = f" ({sandhi_type})" if sandhi_type else ""

    st.markdown(
        f'<div class="tree-node"><b>SandhiGroup:</b> {surface}{type_info}{compound_info}</div>',
        unsafe_allow_html=True,
    )

    # Render base words
    for word_idx, word in enumerate(base_words):
        word_id = f"{group_id}_w{word_idx}"
        with st.container():
            render_word_card(word, word_id)


def _render_engine_votes(votes: dict[str, float]) -> None:
    """Render the engine votes section.

    Args:
        votes: Dictionary mapping engine names to scores.
    """
    st.markdown("---")
    vote_parts = []
    for engine, score in votes.items():
        check = "✓" if score > 0.5 else "✗"
        vote_parts.append(f"{engine} {check}")

    st.markdown(f"**Engine Votes:** {' │ '.join(vote_parts)}")
