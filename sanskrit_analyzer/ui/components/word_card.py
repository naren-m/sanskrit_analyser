"""Word card component with minimal and expanded views."""

from typing import Any

import streamlit as st

from sanskrit_analyzer.ui.state import is_word_expanded, toggle_word_expanded
from sanskrit_analyzer.ui.styles import confidence_class, expand_icon


def render_word_card(word: dict[str, Any], word_id: str) -> None:
    """Render a word card with expandable details.

    Args:
        word: Word data dictionary from the analysis result.
        word_id: Unique identifier for this word card.
    """
    is_expanded = is_word_expanded(word_id)

    # Get display values
    scripts = word.get("scripts", {})
    devanagari = scripts.get("devanagari", word.get("lemma", ""))
    iast = scripts.get("iast", "")
    morphology = word.get("morphology", {})
    pos = morphology.get("pos", "") if morphology else ""

    # Render header (always visible)
    _render_word_header(word_id, devanagari, iast, pos, is_expanded)

    # Render expanded details
    if is_expanded:
        _render_expanded_details(word)


def _render_word_header(
    word_id: str,
    devanagari: str,
    iast: str,
    pos: str,
    is_expanded: bool,
) -> None:
    """Render the always-visible word header.

    Args:
        word_id: Unique identifier for toggling.
        devanagari: Devanagari script text.
        iast: IAST transliteration.
        pos: Part of speech.
        is_expanded: Whether the card is expanded.
    """
    col_toggle, col_word, col_pos = st.columns([0.5, 3, 1])

    with col_toggle:
        icon = expand_icon(is_expanded)
        if st.button(icon, key=f"toggle_{word_id}", help="Show/hide details"):
            toggle_word_expanded(word_id)
            st.rerun()

    with col_word:
        st.markdown(f"**{devanagari}** ({iast})")

    with col_pos:
        if pos:
            st.markdown(f'<span class="word-pos-tag">{pos}</span>', unsafe_allow_html=True)


def _render_expanded_details(word: dict[str, Any]) -> None:
    """Render the expanded word card with full details.

    Args:
        word: Word data dictionary.
    """
    st.markdown('<div class="word-card">', unsafe_allow_html=True)

    # Morphology section
    morphology = word.get("morphology")
    if morphology:
        _render_morphology_section(morphology)

    # Scripts section
    scripts = word.get("scripts")
    if scripts:
        _render_scripts_section(scripts)

    # Meanings section
    meanings = word.get("meanings", [])
    if meanings:
        _render_meanings_section(meanings)

    # Dhatu section (for verb-derived words)
    dhatu = word.get("dhatu")
    if dhatu:
        _render_dhatu_section(dhatu)

    # Confidence footer
    confidence = word.get("confidence", 0)
    _render_confidence_footer(confidence)

    st.markdown("</div>", unsafe_allow_html=True)


MORPHOLOGY_FIELDS = ["pos", "gender", "number", "case", "person", "tense", "mood", "voice"]


def _render_morphology_section(morphology: dict[str, Any]) -> None:
    """Render the morphology section of the card.

    Args:
        morphology: Morphological tag data.
    """
    st.markdown(
        '<div class="word-card-section-title">MORPHOLOGY</div>',
        unsafe_allow_html=True,
    )

    parts = [
        f"**{field.title()}:** {value}"
        for field in MORPHOLOGY_FIELDS
        if (value := morphology.get(field))
    ]

    st.markdown(" │ ".join(parts) if parts else "—")


def _render_scripts_section(scripts: dict[str, str]) -> None:
    """Render the scripts section of the card.

    Args:
        scripts: Dictionary of script variants.
    """
    st.markdown(
        '<div class="word-card-section">'
        '<div class="word-card-section-title">SCRIPTS</div>',
        unsafe_allow_html=True,
    )

    parts = []
    if dev := scripts.get("devanagari"):
        parts.append(f"**देवनागरी:** {dev}")
    if iast := scripts.get("iast"):
        parts.append(f"**IAST:** {iast}")
    if slp1 := scripts.get("slp1"):
        parts.append(f"**SLP1:** {slp1}")

    st.markdown(" │ ".join(parts) if parts else "—")
    st.markdown("</div>", unsafe_allow_html=True)


def _render_meanings_section(meanings: list[str]) -> None:
    """Render the meanings section of the card.

    Args:
        meanings: List of dictionary meanings.
    """
    st.markdown(
        '<div class="word-card-section">'
        '<div class="word-card-section-title">MEANINGS</div>',
        unsafe_allow_html=True,
    )

    for i, meaning in enumerate(meanings[:5], 1):  # Show max 5
        st.markdown(f"{i}. {meaning}")

    st.markdown("</div>", unsafe_allow_html=True)


def _render_dhatu_section(dhatu: dict[str, Any]) -> None:
    """Render the dhatu (verbal root) section.

    Args:
        dhatu: Dhatu information dictionary.
    """
    st.markdown(
        '<div class="word-card-section">'
        '<div class="word-card-section-title">VERBAL ROOT</div>',
        unsafe_allow_html=True,
    )

    root = dhatu.get("root", "")
    meaning = dhatu.get("meaning", "")
    gana = dhatu.get("gana", "")

    parts = []
    if root:
        parts.append(f"√{root}")
    if meaning:
        parts.append(f'"{meaning}"')
    if gana:
        parts.append(f"({gana} gaṇa)")

    st.markdown(" ".join(parts) if parts else "—")
    st.markdown("</div>", unsafe_allow_html=True)


def _render_confidence_footer(confidence: float) -> None:
    """Render the confidence footer.

    Args:
        confidence: Confidence value between 0 and 1.
    """
    percentage = int(confidence * 100)
    css_class = confidence_class(confidence)

    st.markdown(
        '<div class="word-card-section">'
        f'<span class="confidence-badge {css_class}">Confidence: {percentage}%</span>'
        "</div>",
        unsafe_allow_html=True,
    )
