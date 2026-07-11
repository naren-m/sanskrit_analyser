"""Tests for the Sanskrit Analyzer API client."""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
import httpx

from sanskrit_analyzer.ui.api_client import (
    APIError,
    AnalysisResult,
    SanskritAPIClient,
    _coerce_confidence,
    _transform_api_response,
)


class TestConfidenceCoercion:
    """Tests for _coerce_confidence and confidence handling in the transform."""

    def test_coerce_none_defaults_to_zero(self) -> None:
        """None confidence becomes 0.0."""
        assert _coerce_confidence(None) == 0.0

    def test_coerce_invalid_defaults_to_zero(self) -> None:
        """Non-numeric confidence becomes 0.0."""
        assert _coerce_confidence("not-a-number") == 0.0

    def test_coerce_numeric_passthrough(self) -> None:
        """Numeric confidence is preserved as a float."""
        assert _coerce_confidence(0.75) == 0.75
        assert _coerce_confidence(1) == 1.0

    def test_transform_null_top_level_confidence(self) -> None:
        """A JSON null overall confidence transforms to a float, not None."""
        transformed = _transform_api_response({"confidence": None})
        assert transformed["confidence"] == 0.0

    def test_transform_null_parse_confidence(self) -> None:
        """A null parse confidence is coerced to a float."""
        transformed = _transform_api_response(
            {"parse_forest": [{"parse_id": "p1", "confidence": None}]}
        )
        assert transformed["parses"][0]["confidence"] == 0.0


class TestTransformPassThroughFields:
    """Ensures parse-tree branch fields survive the transform."""

    def test_engine_votes_carried_through(self) -> None:
        """engine_votes is preserved on the parse."""
        transformed = _transform_api_response(
            {"parse_forest": [{"parse_id": "p1", "engine_votes": {"vidyut": 0.9}}]}
        )
        assert transformed["parses"][0]["engine_votes"] == {"vidyut": 0.9}

    def test_sandhi_group_type_fields_carried_through(self) -> None:
        """sandhi_type, is_compound and compound_type survive the transform."""
        transformed = _transform_api_response(
            {
                "parse_forest": [
                    {
                        "parse_id": "p1",
                        "sandhi_groups": [
                            {
                                "group_id": "g0",
                                "surface_form": "x",
                                "sandhi_type": "visarga",
                                "is_compound": True,
                                "compound_type": "tatpurusha",
                            }
                        ],
                    }
                ]
            }
        )
        group = transformed["parses"][0]["sandhi_groups"][0]
        assert group["sandhi_type"] == "visarga"
        assert group["is_compound"] is True
        assert group["compound_type"] == "tatpurusha"


class TestAPIError:
    """Tests for APIError dataclass."""

    def test_create_with_message_only(self) -> None:
        """APIError can be created with just a message."""
        error = APIError(message="Test error")
        assert error.message == "Test error"
        assert error.details is None

    def test_create_with_details(self) -> None:
        """APIError can be created with details."""
        error = APIError(message="Test error", details="More info")
        assert error.message == "Test error"
        assert error.details == "More info"


class TestAnalysisResult:
    """Tests for AnalysisResult dataclass."""

    def test_success_result(self) -> None:
        """AnalysisResult for successful response."""
        result = AnalysisResult(success=True, data={"test": "data"})
        assert result.success is True
        assert result.data == {"test": "data"}
        assert result.error is None

    def test_error_result(self) -> None:
        """AnalysisResult for error response."""
        error = APIError(message="Failed")
        result = AnalysisResult(success=False, error=error)
        assert result.success is False
        assert result.data is None
        assert result.error.message == "Failed"


class TestSanskritAPIClient:
    """Tests for SanskritAPIClient."""

    def test_default_base_url(self) -> None:
        """Client uses default URL when none provided."""
        client = SanskritAPIClient()
        assert "localhost:8000" in client.base_url

    def test_custom_base_url(self) -> None:
        """Client uses provided URL."""
        client = SanskritAPIClient(base_url="http://custom:9000")
        assert client.base_url == "http://custom:9000"

    def test_custom_timeout(self) -> None:
        """Client uses provided timeout."""
        client = SanskritAPIClient(timeout=60.0)
        assert client.timeout == 60.0

    @pytest.mark.asyncio
    async def test_analyze_success(self) -> None:
        """analyze() returns success result on 200 response."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        # Mock API response format (will be transformed by client)
        mock_response.json.return_value = {
            "original_text": "रामः गच्छति",
            "scripts": {"devanagari": "रामः गच्छति", "iast": "rāmaḥ gacchati"},
            "parse_forest": [],
            "confidence": {"overall": 0.95},
            "mode": "educational",
        }

        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.post.return_value = mock_response
            mock_instance.__aenter__.return_value = mock_instance
            mock_instance.__aexit__.return_value = None
            mock_client.return_value = mock_instance

            client = SanskritAPIClient()
            result = await client.analyze("test", "educational")

            assert result.success is True
            # Check transformed structure
            assert result.data["sentence"]["original"] == "रामः गच्छति"
            assert result.data["confidence"] == 0.95
            assert result.data["parses"] == []

    @pytest.mark.asyncio
    async def test_analyze_connection_error(self) -> None:
        """analyze() handles connection errors."""
        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.post.side_effect = httpx.ConnectError("Connection refused")
            mock_instance.__aenter__.return_value = mock_instance
            mock_instance.__aexit__.return_value = None
            mock_client.return_value = mock_instance

            client = SanskritAPIClient()
            result = await client.analyze("test", "educational")

            assert result.success is False
            assert "Cannot connect" in result.error.message

    @pytest.mark.asyncio
    async def test_analyze_timeout(self) -> None:
        """analyze() handles timeout errors."""
        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.post.side_effect = httpx.TimeoutException("Timeout")
            mock_instance.__aenter__.return_value = mock_instance
            mock_instance.__aexit__.return_value = None
            mock_client.return_value = mock_instance

            client = SanskritAPIClient()
            result = await client.analyze("test", "educational")

            assert result.success is False
            assert "timed out" in result.error.message

    @pytest.mark.asyncio
    async def test_analyze_server_error(self) -> None:
        """analyze() handles 5xx errors."""
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
            assert "Server error" in result.error.message

    @pytest.mark.asyncio
    async def test_analyze_non_json_body(self) -> None:
        """analyze() returns a structured error when a 200 body is not JSON."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.side_effect = ValueError("Expecting value")

        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.post.return_value = mock_response
            mock_instance.__aenter__.return_value = mock_instance
            mock_instance.__aexit__.return_value = None
            mock_client.return_value = mock_instance

            client = SanskritAPIClient()
            result = await client.analyze("test", "educational")

            # No traceback: a structured APIError is returned instead.
            assert result.success is False
            assert result.error is not None
            assert "Unexpected error" in result.error.message

    @pytest.mark.asyncio
    async def test_health_check_success(self) -> None:
        """health_check() returns success on 200."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"status": "healthy"}

        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.get.return_value = mock_response
            mock_instance.__aenter__.return_value = mock_instance
            mock_instance.__aexit__.return_value = None
            mock_client.return_value = mock_instance

            client = SanskritAPIClient()
            result = await client.health_check()

            assert result.success is True
            assert result.data == {"status": "healthy"}

    @pytest.mark.asyncio
    async def test_health_check_connection_error(self) -> None:
        """health_check() handles connection errors."""
        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.get.side_effect = httpx.ConnectError("Connection refused")
            mock_instance.__aenter__.return_value = mock_instance
            mock_instance.__aexit__.return_value = None
            mock_client.return_value = mock_instance

            client = SanskritAPIClient()
            result = await client.health_check()

            assert result.success is False
            assert "Cannot connect" in result.error.message
