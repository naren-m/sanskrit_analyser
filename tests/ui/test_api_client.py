"""Tests for the Sanskrit Analyzer API client."""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
import httpx

from sanskrit_analyzer.ui.api_client import (
    APIError,
    AnalysisResult,
    SanskritAPIClient,
)


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
