"""Integration tests for the Sanskrit Analyzer UI full flow."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch


class MockSessionState:
    """A mock for Streamlit's session_state."""

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


# Sample API response for testing (in API format, will be transformed by client)
SAMPLE_ANALYSIS_RESPONSE = {
    "original_text": "रामः गच्छति",
    "scripts": {
        "devanagari": "रामः गच्छति",
        "iast": "rāmaḥ gacchati",
        "slp1": "rAmaH gacCati",
    },
    "confidence": {"overall": 0.94, "engine_agreement": 0.85},
    "mode": "educational",
    "parse_forest": [
        {
            "parse_id": "parse_1",
            "confidence": 0.94,
            "sandhi_groups": [
                {
                    "group_id": "g0_0",
                    "surface_form": "rAmaH",
                    "base_words": [
                        {
                            "word_id": "w0_0_0",
                            "lemma": "rAma",
                            "surface_form": "rAmaH",
                            "scripts": {"devanagari": "राम", "iast": "rāma"},
                            "morphology": {"pos": "noun", "case": "nominative"},
                            "meanings": ["Rama", "pleasing"],
                            "confidence": 0.95,
                        }
                    ],
                },
                {
                    "group_id": "g0_1",
                    "surface_form": "gacCati",
                    "base_words": [
                        {
                            "word_id": "w0_1_0",
                            "lemma": "gam",
                            "surface_form": "gacCati",
                            "scripts": {"devanagari": "गम्", "iast": "gam"},
                            "morphology": {"pos": "verb", "person": "3rd"},
                            "meanings": ["goes"],
                            "dhatu": {"dhatu": "gam", "meaning": "to go", "gana": 1},
                            "confidence": 0.93,
                        }
                    ],
                },
            ],
        }
    ],
}


class TestFullAnalysisFlow:
    """Integration tests for the complete analysis workflow."""

    @pytest.fixture
    def mock_streamlit(self) -> MagicMock:
        """Create mock Streamlit environment."""
        mock_state = MockSessionState()
        mock_st = MagicMock()
        mock_st.session_state = mock_state
        mock_st.spinner = MagicMock(return_value=MagicMock(__enter__=MagicMock(), __exit__=MagicMock()))
        mock_st.rerun = MagicMock()
        return mock_st

    @pytest.mark.asyncio
    async def test_analyze_stores_result_in_session(self) -> None:
        """Full flow: input -> API call -> result stored in session state."""
        from sanskrit_analyzer.ui.api_client import AnalysisResult, SanskritAPIClient

        # Mock successful API response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = SAMPLE_ANALYSIS_RESPONSE

        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.post.return_value = mock_response
            mock_instance.__aenter__.return_value = mock_instance
            mock_instance.__aexit__.return_value = None
            mock_client.return_value = mock_instance

            client = SanskritAPIClient()
            result = await client.analyze("रामः गच्छति", "educational")

            assert result.success is True
            assert result.data is not None
            assert result.data["sentence"]["original"] == "रामः गच्छति"
            assert len(result.data["parses"]) == 1

    @pytest.mark.asyncio
    async def test_mode_affects_api_request(self) -> None:
        """Mode selection is passed to API request."""
        from sanskrit_analyzer.ui.api_client import SanskritAPIClient

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = SAMPLE_ANALYSIS_RESPONSE

        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.post.return_value = mock_response
            mock_instance.__aenter__.return_value = mock_instance
            mock_instance.__aexit__.return_value = None
            mock_client.return_value = mock_instance

            client = SanskritAPIClient()

            # Test each mode
            for mode in ["educational", "research", "quick"]:
                await client.analyze("test", mode)

                # Verify the mode was passed in the request
                call_args = mock_instance.post.call_args
                assert call_args[1]["json"]["mode"] == mode

    def test_history_updates_after_analysis(self) -> None:
        """History is updated after successful analysis."""
        mock_state = MockSessionState()

        with patch("sanskrit_analyzer.ui.state.st") as mock_st:
            mock_st.session_state = mock_state

            from sanskrit_analyzer.ui.state import add_to_history, get_history

            # Simulate adding to history after analysis
            add_to_history("रामः गच्छति", "educational")

            history = get_history()
            assert len(history) == 1
            assert history[0]["text"] == "रामः गच्छति"
            assert history[0]["mode"] == "educational"

    @pytest.mark.asyncio
    async def test_error_state_on_connection_failure(self) -> None:
        """Connection errors are captured in result."""
        import httpx
        from sanskrit_analyzer.ui.api_client import SanskritAPIClient

        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.post.side_effect = httpx.ConnectError("Connection refused")
            mock_instance.__aenter__.return_value = mock_instance
            mock_instance.__aexit__.return_value = None
            mock_client.return_value = mock_instance

            client = SanskritAPIClient()
            result = await client.analyze("test", "educational")

            assert result.success is False
            assert result.error is not None
            assert "Cannot connect" in result.error.message

    @pytest.mark.asyncio
    async def test_error_state_on_server_error(self) -> None:
        """Server errors (5xx) are captured with appropriate message."""
        from sanskrit_analyzer.ui.api_client import SanskritAPIClient

        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"
        mock_response.json.return_value = {}

        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.post.return_value = mock_response
            mock_instance.__aenter__.return_value = mock_instance
            mock_instance.__aexit__.return_value = None
            mock_client.return_value = mock_instance

            client = SanskritAPIClient()
            result = await client.analyze("test", "educational")

            assert result.success is False
            assert result.error is not None
            assert "Server error" in result.error.message


class TestComponentIntegration:
    """Tests for component integration logic."""

    def test_diff_view_with_multiple_parses(self) -> None:
        """Diff view computes differences between parses."""
        from sanskrit_analyzer.ui.components.diff_view import _compute_differences

        parse1 = {
            "sandhi_groups": [
                {
                    "base_words": [
                        {"lemma": "rama", "scripts": {"devanagari": "राम"}, "morphology": {"pos": "noun"}}
                    ]
                }
            ]
        }
        parse2 = {
            "sandhi_groups": [
                {
                    "base_words": [
                        {"lemma": "sita", "scripts": {"devanagari": "सीता"}, "morphology": {"pos": "noun"}}
                    ]
                }
            ]
        }

        diffs = _compute_differences(parse1, parse2)
        assert len(diffs) > 0
        assert any("Different lemma" in d for d in diffs)

    def test_confidence_styling_integration(self) -> None:
        """Confidence values map to correct CSS classes."""
        from sanskrit_analyzer.ui.styles import confidence_class

        # High confidence parse
        assert confidence_class(0.94) == "confidence-high"

        # Medium confidence
        assert confidence_class(0.65) == "confidence-medium"

        # Low confidence
        assert confidence_class(0.30) == "confidence-low"

    def test_state_toggle_functions(self) -> None:
        """State toggle functions work correctly for UI expansion."""
        mock_state = MockSessionState()

        with patch("sanskrit_analyzer.ui.state.st") as mock_st:
            mock_st.session_state = mock_state

            from sanskrit_analyzer.ui.state import (
                is_parse_expanded,
                is_word_expanded,
                toggle_parse_expanded,
                toggle_word_expanded,
            )

            # Initially collapsed
            assert is_parse_expanded("parse_1") is False
            assert is_word_expanded("word_1") is False

            # Toggle to expanded
            toggle_parse_expanded("parse_1")
            toggle_word_expanded("word_1")

            assert is_parse_expanded("parse_1") is True
            assert is_word_expanded("word_1") is True

            # Toggle back to collapsed
            toggle_parse_expanded("parse_1")
            toggle_word_expanded("word_1")

            assert is_parse_expanded("parse_1") is False
            assert is_word_expanded("word_1") is False
