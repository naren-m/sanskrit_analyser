"""HTTP client for communicating with the Sanskrit Analyzer FastAPI backend."""

import os
from dataclasses import dataclass
from typing import Any

import httpx

from sanskrit_analyzer.models.scripts import Script
from sanskrit_analyzer.utils.transliterate import transliterate


def _slp1_to_devanagari(text: str) -> str:
    """Convert SLP1 text to Devanagari."""
    if not text:
        return text
    return transliterate(text, Script.SLP1, Script.DEVANAGARI)


def _transform_api_response(data: dict[str, Any]) -> dict[str, Any]:
    """Transform API response to UI-expected format.

    The API returns a structure with parse_forest, original_text, etc.
    The UI expects parses, sentence.original, confidence as float, etc.

    Args:
        data: Raw API response data.

    Returns:
        Transformed data matching UI component expectations.
    """
    # Extract confidence value (API returns nested object)
    confidence_data = data.get("confidence", {})
    confidence = confidence_data.get("overall", 0) if isinstance(confidence_data, dict) else confidence_data

    # Transform parse_forest to parses with UI-expected structure
    parses = [
        {
            "parse_id": parse.get("parse_id", ""),
            "confidence": parse.get("confidence", 0),
            "sandhi_groups": _transform_sandhi_groups(parse.get("sandhi_groups", [])),
        }
        for parse in data.get("parse_forest", [])
    ]

    return {
        "sentence": {
            "original": data.get("original_text", ""),
            "scripts": data.get("scripts", {}),
        },
        "parses": parses,
        "confidence": confidence,
        "mode": data.get("mode", ""),
    }


def _transform_sandhi_groups(groups: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Transform sandhi groups to UI-expected format.

    Args:
        groups: List of sandhi group data from API.

    Returns:
        Transformed sandhi groups.
    """
    return [
        {
            "group_id": group.get("group_id", ""),
            "surface_form": group.get("surface_form", ""),
            "scripts": {"devanagari": _slp1_to_devanagari(group.get("surface_form", ""))},
            "base_words": _transform_base_words(group.get("base_words", [])),
        }
        for group in groups
    ]


def _transform_base_words(words: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Transform base words to UI-expected format.

    Args:
        words: List of base word data from API.

    Returns:
        Transformed base words.
    """
    return [
        {
            "word_id": word.get("word_id", ""),
            "lemma": word.get("lemma", ""),
            "surface_form": word.get("surface_form", ""),
            "scripts": word.get("scripts", {}),
            "morphology": word.get("morphology", {}),
            "meanings": word.get("meanings", []),
            "dhatu": _transform_dhatu(word.get("dhatu")),
            "confidence": word.get("confidence", 0),
        }
        for word in words
    ]


def _transform_dhatu(dhatu: dict[str, Any] | None) -> dict[str, Any] | None:
    """Transform dhatu data to UI-expected format.

    Args:
        dhatu: Dhatu data from API or None.

    Returns:
        Transformed dhatu or None.
    """
    if not dhatu:
        return None
    return {
        "root": dhatu.get("dhatu", ""),
        "meaning": dhatu.get("meaning", ""),
        "gana": dhatu.get("gana"),
    }


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
                    data = response.json()
                    # Transform API response to UI-expected format
                    transformed = _transform_api_response(data)
                    return AnalysisResult(success=True, data=transformed)

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
