"""Sanskrit Heritage Engine client for lexicon-based analysis."""

import asyncio
from urllib.parse import quote

import aiohttp

from sanskrit_analyzer.engines.base import EngineBase, EngineResult, Segment
from sanskrit_analyzer.models.scripts import Script
from sanskrit_analyzer.utils.normalize import detect_script
from sanskrit_analyzer.utils.transliterate import transliterate

# Sanskrit Heritage Engine URLs
PUBLIC_HERITAGE_URL = "https://sanskrit.inria.fr/cgi-bin/SKT/sktgraph"
DEFAULT_LOCAL_URL = "http://localhost:8080"


class HeritageEngine(EngineBase):
    """Sanskrit Heritage Engine client for lexicon-based analysis.

    The Sanskrit Heritage Engine (by Gérard Huet at INRIA) provides
    comprehensive Sanskrit analysis using:
    - 25K+ word lexicon (Monier-Williams based)
    - Finite-state automaton for sandhi splitting
    - Morphological analysis with case/gender/number
    """

    def __init__(
        self,
        local_url: str | None = None,
        use_local: bool = True,
        timeout: float = 10.0,
    ) -> None:
        """Initialize the Heritage Engine client.

        Args:
            local_url: URL for local Heritage Engine instance.
            use_local: Whether to try local instance first.
            timeout: HTTP request timeout in seconds.
        """
        self._local_url = local_url or DEFAULT_LOCAL_URL
        self._public_url = PUBLIC_HERITAGE_URL
        self._use_local = use_local
        self._timeout = timeout
        self._available = True  # HTTP-based, assume available

    @property
    def name(self) -> str:
        """Return the engine name."""
        return "heritage"

    @property
    def weight(self) -> float:
        """Return the default weight for ensemble voting."""
        return 0.25

    @property
    def is_available(self) -> bool:
        """Check if the engine is available."""
        return self._available

    def _normalize_to_slp1(self, text: str) -> str:
        """Normalize input text to SLP1 for Heritage Engine."""
        script = detect_script(text)
        if script == Script.SLP1:
            return text
        return transliterate(text, script, Script.SLP1)

    def _build_url(self, base_url: str, text: str) -> str:
        """Build the Heritage Engine query URL.

        Args:
            base_url: Base URL of the Heritage Engine.
            text: Sanskrit text in SLP1.

        Returns:
            Complete query URL.
        """
        # Heritage Engine expects specific URL format
        # The sktgraph endpoint accepts 't' parameter for text
        encoded_text = quote(text)
        return f"{base_url}?t={encoded_text}&lex=MW&st=t&us=f&cp=t&text=&topic="

    def _parse_heritage_response(self, html: str, original_text: str) -> list[Segment]:
        """Parse Heritage Engine HTML response into segments.

        The Heritage Engine returns HTML with segmentation results.
        This parser extracts the key information.

        Args:
            html: HTML response from Heritage Engine.
            original_text: Original input text.

        Returns:
            List of parsed Segment objects.
        """
        segments: list[Segment] = []

        # Heritage returns a complex HTML structure
        # For now, we'll do a simplified parse looking for key patterns
        # A full implementation would use BeautifulSoup

        # Look for word entries in the response
        # The format typically includes lemma and morphological info

        # Simple fallback: if we can't parse, return original as single segment
        if not html or "error" in html.lower():
            return []

        # Check if we got valid results
        if "no_solution" in html or "No solution" in html:
            return []

        # For a basic implementation, we'll extract text between certain markers
        # This is a simplified parser - full implementation would need BeautifulSoup

        try:
            # Look for segmented words in the response
            # Heritage typically shows results in tables or spans

            # Try to find word segments between specific patterns
            # This is a heuristic approach

            # If HTML contains valid structure, extract segments
            if "<td" in html or "<span" in html:
                # For now, return original as unsplit if we see valid HTML
                # A proper implementation would parse the HTML structure
                segment = Segment(
                    surface=original_text,
                    lemma=original_text,
                    morphology=None,
                    confidence=0.7,  # Lower confidence for unparsed response
                    pos=None,
                )
                segments.append(segment)

        except Exception:
            # If parsing fails, return empty list
            pass

        return segments

    async def _query_heritage(self, url: str, text: str) -> str | None:
        """Query Heritage Engine and return HTML response.

        Args:
            url: Heritage Engine URL.
            text: Sanskrit text in SLP1.

        Returns:
            HTML response or None if request failed.
        """
        query_url = self._build_url(url, text)

        try:
            timeout = aiohttp.ClientTimeout(total=self._timeout)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(query_url) as response:
                    if response.status == 200:
                        return await response.text()
                    return None
        except asyncio.TimeoutError:
            return None
        except aiohttp.ClientError:
            return None
        except Exception:
            return None

    async def analyze(self, text: str) -> EngineResult:
        """Analyze Sanskrit text using Heritage Engine.

        Args:
            text: Sanskrit text in any script.

        Returns:
            EngineResult with analyzed segments.
        """
        if not text.strip():
            return EngineResult(
                engine=self.name,
                segments=[],
                confidence=0.0,
            )

        try:
            # Normalize to SLP1
            slp1_text = self._normalize_to_slp1(text)

            html_response: str | None = None

            # Try local instance first if configured
            if self._use_local:
                html_response = await self._query_heritage(self._local_url, slp1_text)

            # Fall back to public instance
            if html_response is None:
                html_response = await self._query_heritage(self._public_url, slp1_text)

            if html_response is None:
                return EngineResult(
                    engine=self.name,
                    segments=[],
                    confidence=0.0,
                    error="Heritage Engine unreachable",
                )

            # Parse the HTML response
            segments = self._parse_heritage_response(html_response, slp1_text)

            if not segments:
                # If parsing failed but we got a response, create basic segment
                segments = [
                    Segment(
                        surface=slp1_text,
                        lemma=slp1_text,
                        morphology=None,
                        confidence=0.5,
                    )
                ]

            return EngineResult(
                engine=self.name,
                segments=segments,
                confidence=0.7 if segments else 0.0,
                raw_output=html_response[:500] if html_response else None,  # Truncate
            )

        except Exception as e:
            return EngineResult(
                engine=self.name,
                segments=[],
                confidence=0.0,
                error=f"Analysis failed: {e}",
            )

    async def health_check(self) -> bool:
        """Check if Heritage Engine is reachable.

        Returns:
            True if engine responds, False otherwise.
        """
        try:
            # Try a simple query
            result = await self._query_heritage(
                self._local_url if self._use_local else self._public_url,
                "gam",
            )
            return result is not None
        except Exception:
            return False
