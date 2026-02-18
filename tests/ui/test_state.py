"""Tests for the Sanskrit Analyzer UI state management."""

import pytest
from unittest.mock import MagicMock, patch


class MockSessionState:
    """A mock for Streamlit's session_state that behaves like a dict."""

    def __init__(self) -> None:
        self.history: list = []
        self.analysis_result = None
        self.selected_mode = "educational"
        self.show_compare = False
        self.expanded_parses: set = set()
        self.expanded_words: set = set()

    def __contains__(self, key: str) -> bool:
        return hasattr(self, key)


class TestStateManagement:
    """Tests for session state management functions."""

    @pytest.fixture(autouse=True)
    def mock_streamlit(self) -> MagicMock:
        """Mock streamlit session_state for each test."""
        mock_state = MockSessionState()

        with patch("sanskrit_analyzer.ui.state.st") as mock_st:
            mock_st.session_state = mock_state
            yield mock_st

    def test_init_state_creates_defaults(self, mock_streamlit: MagicMock) -> None:
        """init_state creates all required state keys."""
        from sanskrit_analyzer.ui.state import init_state

        # Simulate missing keys
        delattr(mock_streamlit.session_state, "history")

        init_state()

        assert mock_streamlit.session_state.history == []

    def test_get_history_returns_list(self, mock_streamlit: MagicMock) -> None:
        """get_history returns the history list."""
        from sanskrit_analyzer.ui.state import get_history

        mock_streamlit.session_state.history = [{"text": "test", "mode": "quick"}]

        history = get_history()

        assert len(history) == 1
        assert history[0]["text"] == "test"

    def test_add_to_history_adds_entry(self, mock_streamlit: MagicMock) -> None:
        """add_to_history adds new entry to front."""
        from sanskrit_analyzer.ui.state import add_to_history

        mock_streamlit.session_state.history = []

        add_to_history("रामः गच्छति", "educational")

        assert len(mock_streamlit.session_state.history) == 1
        assert mock_streamlit.session_state.history[0]["text"] == "रामः गच्छति"
        assert mock_streamlit.session_state.history[0]["mode"] == "educational"

    def test_add_to_history_removes_duplicates(
        self, mock_streamlit: MagicMock
    ) -> None:
        """add_to_history removes duplicate entries."""
        from sanskrit_analyzer.ui.state import add_to_history

        mock_streamlit.session_state.history = [
            {"text": "test", "mode": "quick", "timestamp": "old"}
        ]

        add_to_history("test", "educational")

        assert len(mock_streamlit.session_state.history) == 1
        assert mock_streamlit.session_state.history[0]["mode"] == "educational"

    def test_add_to_history_enforces_max_size(
        self, mock_streamlit: MagicMock
    ) -> None:
        """add_to_history keeps only MAX_HISTORY_SIZE entries."""
        from sanskrit_analyzer.ui.state import add_to_history, MAX_HISTORY_SIZE

        mock_streamlit.session_state.history = [
            {"text": f"entry{i}", "mode": "quick", "timestamp": "t"}
            for i in range(MAX_HISTORY_SIZE)
        ]

        add_to_history("new entry", "educational")

        assert len(mock_streamlit.session_state.history) == MAX_HISTORY_SIZE
        assert mock_streamlit.session_state.history[0]["text"] == "new entry"

    def test_clear_history_empties_list(self, mock_streamlit: MagicMock) -> None:
        """clear_history removes all entries."""
        from sanskrit_analyzer.ui.state import clear_history

        mock_streamlit.session_state.history = [{"text": "test"}]

        clear_history()

        assert mock_streamlit.session_state.history == []

    def test_set_analysis_result_stores_data(
        self, mock_streamlit: MagicMock
    ) -> None:
        """set_analysis_result stores the result."""
        from sanskrit_analyzer.ui.state import set_analysis_result

        set_analysis_result({"parses": []})

        assert mock_streamlit.session_state.analysis_result == {"parses": []}

    def test_set_analysis_result_clears_with_none(
        self, mock_streamlit: MagicMock
    ) -> None:
        """set_analysis_result can clear the result."""
        from sanskrit_analyzer.ui.state import set_analysis_result

        mock_streamlit.session_state.analysis_result = {"old": "data"}

        set_analysis_result(None)

        assert mock_streamlit.session_state.analysis_result is None

    def test_get_analysis_result_returns_stored(
        self, mock_streamlit: MagicMock
    ) -> None:
        """get_analysis_result returns stored result."""
        from sanskrit_analyzer.ui.state import get_analysis_result

        mock_streamlit.session_state.analysis_result = {"parses": []}

        result = get_analysis_result()

        assert result == {"parses": []}

    def test_toggle_parse_expanded_adds_id(
        self, mock_streamlit: MagicMock
    ) -> None:
        """toggle_parse_expanded adds ID when not present."""
        from sanskrit_analyzer.ui.state import toggle_parse_expanded

        mock_streamlit.session_state.expanded_parses = set()

        toggle_parse_expanded("parse_1")

        assert "parse_1" in mock_streamlit.session_state.expanded_parses

    def test_toggle_parse_expanded_removes_id(
        self, mock_streamlit: MagicMock
    ) -> None:
        """toggle_parse_expanded removes ID when present."""
        from sanskrit_analyzer.ui.state import toggle_parse_expanded

        mock_streamlit.session_state.expanded_parses = {"parse_1"}

        toggle_parse_expanded("parse_1")

        assert "parse_1" not in mock_streamlit.session_state.expanded_parses

    def test_is_parse_expanded_returns_true(
        self, mock_streamlit: MagicMock
    ) -> None:
        """is_parse_expanded returns True when expanded."""
        from sanskrit_analyzer.ui.state import is_parse_expanded

        mock_streamlit.session_state.expanded_parses = {"parse_1"}

        assert is_parse_expanded("parse_1") is True

    def test_is_parse_expanded_returns_false(
        self, mock_streamlit: MagicMock
    ) -> None:
        """is_parse_expanded returns False when not expanded."""
        from sanskrit_analyzer.ui.state import is_parse_expanded

        mock_streamlit.session_state.expanded_parses = set()

        assert is_parse_expanded("parse_1") is False

    def test_toggle_word_expanded_adds_id(
        self, mock_streamlit: MagicMock
    ) -> None:
        """toggle_word_expanded adds ID when not present."""
        from sanskrit_analyzer.ui.state import toggle_word_expanded

        mock_streamlit.session_state.expanded_words = set()

        toggle_word_expanded("word_1")

        assert "word_1" in mock_streamlit.session_state.expanded_words

    def test_toggle_word_expanded_removes_id(
        self, mock_streamlit: MagicMock
    ) -> None:
        """toggle_word_expanded removes ID when present."""
        from sanskrit_analyzer.ui.state import toggle_word_expanded

        mock_streamlit.session_state.expanded_words = {"word_1"}

        toggle_word_expanded("word_1")

        assert "word_1" not in mock_streamlit.session_state.expanded_words

    def test_is_word_expanded_returns_true(
        self, mock_streamlit: MagicMock
    ) -> None:
        """is_word_expanded returns True when expanded."""
        from sanskrit_analyzer.ui.state import is_word_expanded

        mock_streamlit.session_state.expanded_words = {"word_1"}

        assert is_word_expanded("word_1") is True

    def test_is_word_expanded_returns_false(
        self, mock_streamlit: MagicMock
    ) -> None:
        """is_word_expanded returns False when not expanded."""
        from sanskrit_analyzer.ui.state import is_word_expanded

        mock_streamlit.session_state.expanded_words = set()

        assert is_word_expanded("word_1") is False
