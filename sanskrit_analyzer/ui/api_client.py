"""HTTP client for communicating with the Sanskrit Analyzer FastAPI backend."""

import os
from dataclasses import dataclass
from typing import Any

import httpx


@dataclass
class APIError:
    """Represents an API error with user-friendly message."""

    message: str
    details: str | None = None


@dataclass
class AnalysisResult:
    """Wrapper for analysis API response."""

    success: bool
    data: dict[str, Any] | None = None
    error: APIError | None = None


class SanskritAPIClient:
    """Client for the Sanskrit Analyzer FastAPI backend."""

    def __init__(self, base_url: str | None = None, timeout: float = 30.0) -> None:
        """Initialize the API client.

        Args:
            base_url: API base URL. Defaults to SANSKRIT_API_URL env var or localhost:8000.
            timeout: Request timeout in seconds.
        """
        self.base_url = base_url or os.getenv(
            "SANSKRIT_API_URL", "http://localhost:8000"
        )
        self.timeout = timeout

    async def analyze(self, text: str, mode: str = "educational") -> AnalysisResult:
        """Analyze Sanskrit text.

        Args:
            text: Sanskrit text to analyze.
            mode: Analysis mode (educational, research, quick).

        Returns:
            AnalysisResult with data or error.
        """
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{self.base_url}/api/v1/analyze",
                    json={"text": text, "mode": mode},
                )

                if response.status_code == 200:
                    return AnalysisResult(success=True, data=response.json())

                # Handle 4xx/5xx errors
                error_msg = self._get_error_message(response)
                return AnalysisResult(
                    success=False,
                    error=APIError(message=error_msg, details=response.text),
                )

        except httpx.ConnectError:
            return AnalysisResult(
                success=False,
                error=APIError(
                    message=f"Cannot connect to API server at {self.base_url}",
                    details="Ensure the backend is running with: uvicorn sanskrit_analyzer.api.app:create_app --factory",
                ),
            )
        except httpx.TimeoutException:
            return AnalysisResult(
                success=False,
                error=APIError(
                    message="Request timed out",
                    details="The server may be overloaded. Try again in a moment.",
                ),
            )
        except httpx.HTTPError as e:
            return AnalysisResult(
                success=False,
                error=APIError(message="HTTP error occurred", details=str(e)),
            )

    async def health_check(self) -> AnalysisResult:
        """Check API health status.

        Returns:
            AnalysisResult with health data or error.
        """
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f"{self.base_url}/health")

                if response.status_code == 200:
                    return AnalysisResult(success=True, data=response.json())

                return AnalysisResult(
                    success=False,
                    error=APIError(message="Health check failed"),
                )

        except httpx.ConnectError:
            return AnalysisResult(
                success=False,
                error=APIError(message="Cannot connect to API server"),
            )
        except httpx.HTTPError as e:
            return AnalysisResult(
                success=False,
                error=APIError(message="Health check error", details=str(e)),
            )

    def _get_error_message(self, response: httpx.Response) -> str:
        """Extract error message from response."""
        if response.status_code >= 500:
            return "Server error occurred. Please try again or check server logs."

        try:
            data = response.json()
            detail = data.get("detail")
            if isinstance(detail, str):
                return detail
            return f"Request failed with status {response.status_code}"
        except Exception:
            return f"Request failed with status {response.status_code}"
