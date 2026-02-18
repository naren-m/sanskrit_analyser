"""Custom CSS styles for the Sanskrit Analyzer Streamlit UI."""

import streamlit as st


def inject_css() -> None:
    """Inject custom CSS styles into the Streamlit app."""
    st.markdown(
        """
        <style>
        /* Tree structure lines */
        .tree-node {
            position: relative;
            padding-left: 24px;
            margin-left: 12px;
            border-left: 1px solid #e0e0e0;
        }

        .tree-node:last-child {
            border-left: none;
        }

        .tree-node::before {
            content: "";
            position: absolute;
            left: 0;
            top: 12px;
            width: 20px;
            border-top: 1px solid #e0e0e0;
        }

        /* Expand/collapse indicators */
        .tree-toggle {
            cursor: pointer;
            user-select: none;
            display: inline-flex;
            align-items: center;
            gap: 8px;
        }

        .tree-toggle:hover {
            color: #1976D2;
        }

        .expand-icon {
            font-family: monospace;
            font-size: 14px;
            width: 16px;
            display: inline-block;
        }

        /* Word card styling */
        .word-card {
            background: #f8f9fa;
            border: 1px solid #e9ecef;
            border-radius: 8px;
            padding: 16px;
            margin: 8px 0;
        }

        .word-card-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 12px;
        }

        .word-card-section {
            border-top: 1px solid #e9ecef;
            padding-top: 12px;
            margin-top: 12px;
        }

        .word-card-section-title {
            font-size: 12px;
            font-weight: 600;
            color: #6c757d;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            margin-bottom: 8px;
        }

        /* Confidence badge */
        .confidence-badge {
            display: inline-block;
            padding: 4px 8px;
            border-radius: 4px;
            font-size: 13px;
            font-weight: 500;
        }

        .confidence-high {
            background: #d4edda;
            color: #155724;
        }

        .confidence-medium {
            background: #fff3cd;
            color: #856404;
        }

        .confidence-low {
            background: #f8d7da;
            color: #721c24;
        }

        /* Parse candidate row */
        .parse-row {
            padding: 12px 16px;
            border: 1px solid #e9ecef;
            border-radius: 6px;
            margin: 8px 0;
            background: #ffffff;
            transition: box-shadow 0.2s;
        }

        .parse-row:hover {
            box-shadow: 0 2px 8px rgba(0,0,0,0.08);
        }

        .parse-row-selected {
            border-color: #1976D2;
            background: #f3f8ff;
        }

        /* Script variant display */
        .script-variants {
            display: flex;
            gap: 16px;
            padding: 8px 0;
            font-family: 'Noto Sans Devanagari', 'Siddhanta', sans-serif;
        }

        .script-variant {
            padding: 4px 12px;
            background: #f1f3f4;
            border-radius: 4px;
            font-size: 14px;
        }

        /* Diff view styling */
        .diff-container {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 16px;
        }

        .diff-column {
            padding: 16px;
            background: #f8f9fa;
            border-radius: 8px;
        }

        .diff-highlight {
            background: #fff3cd;
            padding: 2px 4px;
            border-radius: 2px;
        }

        /* History item styling */
        .history-item {
            padding: 8px 12px;
            border-radius: 4px;
            cursor: pointer;
            margin: 4px 0;
            font-size: 14px;
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
        }

        .history-item:hover {
            background: #e9ecef;
        }

        /* Input area styling */
        .input-container {
            background: #ffffff;
            padding: 20px;
            border-radius: 8px;
            border: 1px solid #e9ecef;
        }

        /* Results header */
        .results-header {
            background: #ffffff;
            padding: 16px 20px;
            border-radius: 8px;
            border: 1px solid #e9ecef;
            margin-bottom: 16px;
        }

        /* Minimal view word display */
        .word-minimal {
            display: inline-flex;
            align-items: center;
            gap: 8px;
            padding: 4px 8px;
            margin: 2px;
        }

        .word-pos-tag {
            font-size: 11px;
            padding: 2px 6px;
            background: #e9ecef;
            border-radius: 3px;
            color: #495057;
        }

        /* Streamlit element overrides */
        .stButton > button {
            border-radius: 6px;
        }

        .stTextArea > div > div > textarea {
            font-family: 'Noto Sans Devanagari', 'Siddhanta', sans-serif;
            font-size: 18px;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def confidence_class(confidence: float) -> str:
    """Get CSS class for confidence level.

    Args:
        confidence: Confidence value between 0 and 1.

    Returns:
        CSS class name for the confidence badge.
    """
    if confidence >= 0.8:
        return "confidence-high"
    if confidence >= 0.5:
        return "confidence-medium"
    return "confidence-low"


def expand_icon(is_expanded: bool) -> str:
    """Get the expand/collapse icon character.

    Args:
        is_expanded: Whether the item is expanded.

    Returns:
        Unicode arrow character.
    """
    return "▼" if is_expanded else "▸"
