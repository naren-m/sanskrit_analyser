"""Diff view component for comparing parse candidates."""

from typing import Any, Callable

import streamlit as st

from sanskrit_analyzer.ui.styles import confidence_class


def render_diff_view(
    parses: list[dict[str, Any]],
    on_close: Callable[[], None],
) -> None:
    """Render the parse comparison diff view.

    Args:
        parses: List of parse candidates to compare.
        on_close: Callback when close button is clicked.
    """
    st.markdown("### Compare Parses")

    # Close button
    if st.button("Close", key="close_diff"):
        on_close()

    if len(parses) < 2:
        st.info("Need at least 2 parse candidates to compare.")
        return

    # Select which parses to compare
    col_left, col_right = st.columns(2)

    parse_options = {
        f"Parse {i+1} ({int(p.get('confidence', 0) * 100)}%)": i
        for i, p in enumerate(parses)
    }

    with col_left:
        left_label = st.selectbox(
            "Left parse",
            options=list(parse_options.keys()),
            index=0,
            key="diff_left",
        )
        left_idx = parse_options[left_label]

    with col_right:
        right_label = st.selectbox(
            "Right parse",
            options=list(parse_options.keys()),
            index=min(1, len(parses) - 1),
            key="diff_right",
        )
        right_idx = parse_options[right_label]

    if left_idx == right_idx:
        st.warning("Select different parses to compare.")
        return

    # Render comparison
    _render_comparison(parses[left_idx], parses[right_idx])


def _render_comparison(left: dict[str, Any], right: dict[str, Any]) -> None:
    """Render side-by-side comparison of two parses.

    Args:
        left: Left parse data.
        right: Right parse data.
    """
    st.markdown('<div class="diff-container">', unsafe_allow_html=True)

    col_left, col_right = st.columns(2)

    with col_left:
        _render_parse_column(left)

    with col_right:
        _render_parse_column(right)

    st.markdown("</div>", unsafe_allow_html=True)

    # Show differences summary
    _render_diff_summary(left, right)


def _render_parse_column(parse: dict[str, Any]) -> None:
    """Render a single parse in a comparison column.

    Args:
        parse: Parse data.
    """
    confidence = parse.get("confidence", 0)
    css_class = confidence_class(confidence)
    sandhi_groups = parse.get("sandhi_groups", [])

    # Build all content as HTML
    lines = [
        f'<span class="confidence-badge {css_class}">{int(confidence * 100)}%</span>'
    ]
    for sg in sandhi_groups:
        scripts = sg.get("scripts", {})
        surface = scripts.get("devanagari", sg.get("surface_form", ""))
        base_words = sg.get("base_words", [])

        word_parts = []
        for word in base_words:
            ws = word.get("scripts", {})
            dev = ws.get("devanagari", word.get("lemma", ""))
            morph = word.get("morphology", {})
            pos = morph.get("pos", "") if morph else ""
            word_parts.append(f"{dev} ({pos})" if pos else dev)

        breakdown = " + ".join(word_parts) if word_parts else "—"
        lines.append(f"<b>{surface}</b> → {breakdown}")

    st.markdown(
        f'<div class="diff-column">{"<br>".join(lines)}</div>',
        unsafe_allow_html=True,
    )


def _render_diff_summary(left: dict[str, Any], right: dict[str, Any]) -> None:
    """Render a summary of differences between parses.

    Args:
        left: Left parse data.
        right: Right parse data.
    """
    differences = _compute_differences(left, right)

    if not differences:
        st.success("These parses are identical.")
        return

    st.markdown("---")
    st.markdown("**Differences:**")

    for diff in differences:
        st.markdown(f"- 🔶 {diff}")


def _compute_differences(left: dict[str, Any], right: dict[str, Any]) -> list[str]:
    """Compute differences between two parses.

    Args:
        left: Left parse data.
        right: Right parse data.

    Returns:
        List of difference descriptions.
    """
    differences = []

    left_groups = left.get("sandhi_groups", [])
    right_groups = right.get("sandhi_groups", [])

    # Compare word counts
    left_count = sum(len(sg.get("base_words", [])) for sg in left_groups)
    right_count = sum(len(sg.get("base_words", [])) for sg in right_groups)

    if left_count != right_count:
        differences.append(
            f"Word count differs: {left_count} vs {right_count}"
        )

    # Compare sandhi group count
    if len(left_groups) != len(right_groups):
        differences.append(
            f"Sandhi groups differ: {len(left_groups)} vs {len(right_groups)}"
        )

    # Compare word-by-word where possible
    left_words = _flatten_words(left_groups)
    right_words = _flatten_words(right_groups)

    # Compare by position
    max_len = max(len(left_words), len(right_words))
    for i in range(max_len):
        left_word = left_words[i] if i < len(left_words) else None
        right_word = right_words[i] if i < len(right_words) else None

        if left_word and right_word:
            diff = _compare_words(left_word, right_word, i + 1)
            if diff:
                differences.append(diff)
        elif left_word:
            ws = left_word.get("scripts", {})
            differences.append(f"Word {i+1}: {ws.get('devanagari', '?')} (only in left)")
        elif right_word:
            ws = right_word.get("scripts", {})
            differences.append(f"Word {i+1}: {ws.get('devanagari', '?')} (only in right)")

    return differences


def _flatten_words(groups: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Flatten all words from sandhi groups.

    Args:
        groups: List of sandhi groups.

    Returns:
        Flat list of words.
    """
    words = []
    for group in groups:
        words.extend(group.get("base_words", []))
    return words


def _compare_words(
    left: dict[str, Any],
    right: dict[str, Any],
    position: int,
) -> str | None:
    """Compare two words and return difference description if any.

    Args:
        left: Left word data.
        right: Right word data.
        position: Word position (1-based).

    Returns:
        Difference description or None if identical.
    """
    left_scripts = left.get("scripts", {})
    right_scripts = right.get("scripts", {})

    left_lemma = left_scripts.get("devanagari", left.get("lemma", ""))
    right_lemma = right_scripts.get("devanagari", right.get("lemma", ""))

    # Different lemmas
    if left.get("lemma") != right.get("lemma"):
        return f"Word {position}: Different lemma - {left_lemma} vs {right_lemma}"

    # Same lemma, different morphology
    left_morph = left.get("morphology", {})
    right_morph = right.get("morphology", {})

    if left_morph != right_morph:
        left_pos = left_morph.get("pos", "?") if left_morph else "?"
        right_pos = right_morph.get("pos", "?") if right_morph else "?"
        return f"Word {position} ({left_lemma}): Different analysis - {left_pos} vs {right_pos}"

    return None
