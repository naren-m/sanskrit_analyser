"""UI components for Sanskrit Analyzer Streamlit app."""

from sanskrit_analyzer.ui.components.diff_view import render_diff_view
from sanskrit_analyzer.ui.components.input_panel import render_input_panel
from sanskrit_analyzer.ui.components.parse_tree import render_parse_list
from sanskrit_analyzer.ui.components.results_header import render_results_header
from sanskrit_analyzer.ui.components.word_card import render_word_card

__all__ = [
    "render_diff_view",
    "render_input_panel",
    "render_parse_list",
    "render_results_header",
    "render_word_card",
]
