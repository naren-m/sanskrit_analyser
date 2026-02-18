"""Shared fixtures for UI tests."""

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
        self.sanskrit_input = ""

    def __contains__(self, key: str) -> bool:
        return hasattr(self, key)


@pytest.fixture
def mock_session_state() -> MockSessionState:
    """Create a mock session state."""
    return MockSessionState()


@pytest.fixture
def mock_streamlit(mock_session_state: MockSessionState) -> MagicMock:
    """Mock streamlit with session_state."""
    with patch("sanskrit_analyzer.ui.state.st") as mock_st:
        mock_st.session_state = mock_session_state
        mock_st.spinner = MagicMock(
            return_value=MagicMock(__enter__=MagicMock(), __exit__=MagicMock())
        )
        mock_st.rerun = MagicMock()
        yield mock_st
