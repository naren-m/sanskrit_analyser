"""Simple Streamlit UI for Sanskrit Analyzer."""

import asyncio
import streamlit as st

from sanskrit_analyzer import Analyzer
from sanskrit_analyzer.config import AnalysisMode

# Page config
st.set_page_config(
    page_title="Sanskrit Analyzer",
    page_icon="🕉️",
    layout="wide",
)

# Title
st.title("🕉️ Sanskrit Analyzer")
st.caption("3-Engine Ensemble Analysis | Sandhi Splitting | Morphological Analysis")

# Initialize analyzer (cached)
@st.cache_resource
def get_analyzer():
    """Get or create the analyzer instance."""
    return Analyzer()

analyzer = get_analyzer()

# Sidebar for settings
with st.sidebar:
    st.header("Settings")

    mode = st.selectbox(
        "Analysis Mode",
        options=["production", "educational", "academic"],
        index=0,
    )

    script_display = st.selectbox(
        "Display Script",
        options=["Devanagari", "IAST", "SLP1"],
        index=0,
    )

    bypass_cache = st.checkbox("Bypass Cache", value=False)

    st.divider()
    st.caption("Examples:")
    if st.button("रामः गच्छति"):
        st.session_state.input_text = "रामः गच्छति"
    if st.button("धर्मक्षेत्रे कुरुक्षेत्रे"):
        st.session_state.input_text = "धर्मक्षेत्रे कुरुक्षेत्रे"
    if st.button("अहं ब्रह्मास्मि"):
        st.session_state.input_text = "अहं ब्रह्मास्मि"

# Main input
input_text = st.text_input(
    "Enter Sanskrit text",
    value=st.session_state.get("input_text", ""),
    placeholder="रामः गच्छति (Rama goes)",
)

# Analyze button
if st.button("🔍 Analyze", type="primary", disabled=not input_text.strip()):
    with st.spinner("Analyzing..."):
        try:
            # Run async analysis
            result = asyncio.run(
                analyzer.analyze(
                    input_text,
                    mode=AnalysisMode(mode),
                    bypass_cache=bypass_cache,
                )
            )
            st.session_state.result = result
        except Exception as e:
            st.error(f"Analysis failed: {e}")

# Display results
if "result" in st.session_state and st.session_state.result:
    result = st.session_state.result

    st.divider()

    # Header with scripts
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Confidence", f"{result.confidence.overall * 100:.0f}%")
    with col2:
        st.metric("Engine Agreement", f"{result.confidence.engine_agreement * 100:.0f}%")
    with col3:
        st.metric("Parse Count", result.parse_count)

    # Script display
    st.subheader("Text in Different Scripts")
    scripts_col1, scripts_col2, scripts_col3 = st.columns(3)
    with scripts_col1:
        st.text_input("Devanagari", result.scripts.devanagari, disabled=True)
    with scripts_col2:
        st.text_input("IAST", result.scripts.iast, disabled=True)
    with scripts_col3:
        st.text_input("SLP1", result.scripts.slp1, disabled=True)

    st.divider()

    # Parse tree display
    if result.parse_forest:
        st.subheader("📊 Parse Analysis")

        for parse_idx, parse in enumerate(result.parse_forest):
            with st.expander(
                f"Parse {parse_idx + 1} (Confidence: {parse.confidence * 100:.0f}%)",
                expanded=(parse_idx == 0),
            ):
                for sg_idx, sg in enumerate(parse.sandhi_groups):
                    st.markdown(f"**Sandhi Group {sg_idx + 1}:** `{sg.surface_form}`")

                    for bw in sg.base_words:
                        # Word card
                        with st.container():
                            word_col1, word_col2 = st.columns([1, 2])

                            with word_col1:
                                st.markdown(f"### {bw.scripts.devanagari if bw.scripts else bw.lemma}")
                                st.caption(f"Lemma: {bw.lemma}")
                                st.caption(f"Surface: {bw.surface_form}")

                                conf_color = "green" if bw.confidence >= 0.8 else "orange" if bw.confidence >= 0.5 else "red"
                                st.markdown(f"Confidence: :{conf_color}[{bw.confidence * 100:.0f}%]")

                            with word_col2:
                                # Morphology
                                if bw.morphology:
                                    st.markdown("**Morphology:**")
                                    morph = bw.morphology
                                    morph_parts = []
                                    if morph.pos:
                                        morph_parts.append(f"POS: {morph.pos.value if hasattr(morph.pos, 'value') else morph.pos}")
                                    if morph.gender:
                                        morph_parts.append(f"Gender: {morph.gender.value if hasattr(morph.gender, 'value') else morph.gender}")
                                    if morph.number:
                                        morph_parts.append(f"Number: {morph.number.value if hasattr(morph.number, 'value') else morph.number}")
                                    if morph.case:
                                        morph_parts.append(f"Case: {morph.case.value if hasattr(morph.case, 'value') else morph.case}")
                                    if morph.tense:
                                        morph_parts.append(f"Tense: {morph.tense.value if hasattr(morph.tense, 'value') else morph.tense}")
                                    if morph.person:
                                        morph_parts.append(f"Person: {morph.person.value if hasattr(morph.person, 'value') else morph.person}")
                                    if morph.voice:
                                        morph_parts.append(f"Voice: {morph.voice.value if hasattr(morph.voice, 'value') else morph.voice}")

                                    if morph_parts:
                                        st.code(" | ".join(morph_parts))
                                    else:
                                        st.caption("No morphology data")

                                # Meanings
                                if bw.meanings:
                                    st.markdown("**Meanings:**")
                                    for m in bw.meanings[:3]:  # Show first 3 meanings
                                        st.markdown(f"- {m}")

                                # Dhatu
                                if bw.dhatu:
                                    st.markdown("**Dhatu (Verbal Root):**")
                                    st.code(f"√{bw.dhatu.dhatu} ({bw.dhatu.gana_name if hasattr(bw.dhatu, 'gana_name') else f'gana {bw.dhatu.gana}'})")
                                    if bw.dhatu.meanings:
                                        st.caption(", ".join(bw.dhatu.meanings[:3]))

                        st.divider()
    else:
        st.warning("No parse trees generated. Try a different input.")

    # Metadata footer
    st.caption(f"Sentence ID: `{result.sentence_id}` | Mode: {result.mode} | Cache: {result.cached_at.value if result.cached_at else 'none'}")
