"""LLM-based disambiguation for semantic understanding."""

import json
import logging
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

import aiohttp

from sanskrit_analyzer.disambiguation.rules import ParseCandidate

logger = logging.getLogger(__name__)


class LLMProvider(Enum):
    """Supported LLM providers."""

    OLLAMA = "ollama"
    OPENAI = "openai"


@dataclass
class LLMConfig:
    """Configuration for LLM disambiguation."""

    provider: LLMProvider = LLMProvider.OLLAMA
    model: str = "llama3.2"
    ollama_url: str = "http://localhost:11434"
    openai_api_key: Optional[str] = None
    timeout: float = 30.0
    max_tokens: int = 500
    temperature: float = 0.1


@dataclass
class LLMDisambiguationResult:
    """Result from LLM disambiguation."""

    success: bool
    ranked_indices: list[int] = field(default_factory=list)
    explanation: Optional[str] = None
    error: Optional[str] = None
    raw_response: Optional[str] = None


class LLMDisambiguator:
    """Uses LLM for semantic disambiguation of parse candidates.

    The LLM is given the parse candidates with their lemmas and
    morphological information, and asked to rank them by likelihood
    based on semantic coherence and context.

    Example:
        config = LLMConfig(model="llama3.2")
        disambiguator = LLMDisambiguator(config)
        result = await disambiguator.disambiguate(candidates, context)
    """

    SYSTEM_PROMPT = """You are a Sanskrit linguistics expert. Your task is to rank parse candidates for a Sanskrit text based on semantic coherence, grammatical correctness, and contextual appropriateness.

For each candidate, evaluate:
1. Semantic coherence - do the lemmas make sense together?
2. Grammatical correctness - is the morphology plausible?
3. Contextual fit - does it fit the broader context if provided?

Respond with ONLY a JSON object in this format:
{
    "ranking": [<index1>, <index2>, ...],
    "explanation": "<brief explanation of your choice>"
}

The ranking should list candidate indices from most likely to least likely."""

    def __init__(self, config: Optional[LLMConfig] = None) -> None:
        """Initialize the LLM disambiguator.

        Args:
            config: LLM configuration.
        """
        self._config = config or LLMConfig()
        self._enabled = True

    @property
    def enabled(self) -> bool:
        """Check if LLM disambiguation is enabled."""
        return self._enabled

    @enabled.setter
    def enabled(self, value: bool) -> None:
        """Enable or disable LLM disambiguation."""
        self._enabled = value

    def _build_prompt(
        self,
        candidates: list[ParseCandidate],
        context: Optional[dict[str, Any]] = None,
    ) -> str:
        """Build the prompt for the LLM.

        Args:
            candidates: Parse candidates to evaluate.
            context: Optional context information.

        Returns:
            Formatted prompt string.
        """
        lines = ["Parse candidates for Sanskrit text:\n"]

        for i, candidate in enumerate(candidates):
            lines.append(f"Candidate {i}:")
            lines.append(f"  Confidence: {candidate.confidence:.2f}")
            lines.append("  Segments:")

            for seg in candidate.segments:
                lemma = seg.get("lemma", "?")
                pos = seg.get("pos", "?")
                surface = seg.get("surface", "?")
                morph = seg.get("morphology", {})

                morph_str = ""
                if morph:
                    morph_parts = []
                    if morph.get("gender"):
                        morph_parts.append(f"gender={morph['gender']}")
                    if morph.get("number"):
                        morph_parts.append(f"number={morph['number']}")
                    if morph.get("case"):
                        morph_parts.append(f"case={morph['case']}")
                    if morph.get("person"):
                        morph_parts.append(f"person={morph['person']}")
                    if morph.get("tense"):
                        morph_parts.append(f"tense={morph['tense']}")
                    morph_str = f" [{', '.join(morph_parts)}]" if morph_parts else ""

                lines.append(f"    - {surface} → {lemma} ({pos}){morph_str}")

            lines.append("")

        if context:
            if context.get("previous_sentence"):
                lines.append(f"Previous: {context['previous_sentence']}")
            if context.get("next_sentence"):
                lines.append(f"Next: {context['next_sentence']}")
            if context.get("topic"):
                lines.append(f"Topic: {context['topic']}")

        lines.append("\nRank these candidates from most to least likely.")

        return "\n".join(lines)

    async def _query_ollama(self, prompt: str) -> Optional[str]:
        """Query Ollama API.

        Args:
            prompt: The prompt to send.

        Returns:
            Response text or None on error.
        """
        url = f"{self._config.ollama_url}/api/generate"

        payload = {
            "model": self._config.model,
            "prompt": prompt,
            "system": self.SYSTEM_PROMPT,
            "stream": False,
            "options": {
                "temperature": self._config.temperature,
                "num_predict": self._config.max_tokens,
            },
        }

        try:
            timeout = aiohttp.ClientTimeout(total=self._config.timeout)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(url, json=payload) as response:
                    if response.status == 200:
                        data = await response.json()
                        return str(data.get("response", ""))
                    else:
                        logger.warning(
                            "Ollama returned status %d", response.status
                        )
                        return None
        except Exception as e:
            logger.warning("Ollama query failed: %s", e)
            return None

    async def _query_openai(self, prompt: str) -> Optional[str]:
        """Query OpenAI API.

        Args:
            prompt: The prompt to send.

        Returns:
            Response text or None on error.
        """
        if not self._config.openai_api_key:
            logger.warning("OpenAI API key not configured")
            return None

        url = "https://api.openai.com/v1/chat/completions"

        headers = {
            "Authorization": f"Bearer {self._config.openai_api_key}",
            "Content-Type": "application/json",
        }

        payload = {
            "model": self._config.model,
            "messages": [
                {"role": "system", "content": self.SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            "temperature": self._config.temperature,
            "max_tokens": self._config.max_tokens,
        }

        try:
            timeout = aiohttp.ClientTimeout(total=self._config.timeout)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(
                    url, json=payload, headers=headers
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        choices = data.get("choices", [])
                        if choices:
                            return str(
                                choices[0].get("message", {}).get("content", "")
                            )
                    logger.warning("OpenAI returned status %d", response.status)
                    return None
        except Exception as e:
            logger.warning("OpenAI query failed: %s", e)
            return None

    def _parse_response(
        self, response: str, num_candidates: int
    ) -> LLMDisambiguationResult:
        """Parse LLM response to extract ranking.

        Args:
            response: Raw LLM response.
            num_candidates: Number of candidates expected.

        Returns:
            Parsed disambiguation result.
        """
        try:
            # Try to extract JSON from response
            # Look for JSON object in the response
            json_match = re.search(r"\{[\s\S]*\}", response)
            if not json_match:
                return LLMDisambiguationResult(
                    success=False,
                    error="No JSON found in response",
                    raw_response=response,
                )

            data = json.loads(json_match.group())
            ranking = data.get("ranking", [])
            explanation = data.get("explanation", "")

            # Validate ranking
            if not isinstance(ranking, list):
                return LLMDisambiguationResult(
                    success=False,
                    error="Ranking is not a list",
                    raw_response=response,
                )

            # Ensure all indices are valid
            valid_ranking = [
                int(idx) for idx in ranking
                if isinstance(idx, (int, float)) and 0 <= int(idx) < num_candidates
            ]

            if not valid_ranking:
                return LLMDisambiguationResult(
                    success=False,
                    error="No valid indices in ranking",
                    raw_response=response,
                )

            return LLMDisambiguationResult(
                success=True,
                ranked_indices=valid_ranking,
                explanation=explanation,
                raw_response=response,
            )

        except json.JSONDecodeError as e:
            return LLMDisambiguationResult(
                success=False,
                error=f"JSON parse error: {e}",
                raw_response=response,
            )
        except Exception as e:
            return LLMDisambiguationResult(
                success=False,
                error=f"Parse error: {e}",
                raw_response=response,
            )

    async def disambiguate(
        self,
        candidates: list[ParseCandidate],
        context: Optional[dict[str, Any]] = None,
    ) -> tuple[list[ParseCandidate], LLMDisambiguationResult]:
        """Use LLM to disambiguate parse candidates.

        Args:
            candidates: Parse candidates to evaluate.
            context: Optional context information.

        Returns:
            Tuple of (ranked candidates, disambiguation result).
        """
        if not self._enabled:
            return candidates, LLMDisambiguationResult(
                success=False,
                error="LLM disambiguation disabled",
            )

        if len(candidates) <= 1:
            return candidates, LLMDisambiguationResult(
                success=True,
                ranked_indices=[0] if candidates else [],
                explanation="Single or no candidates",
            )

        # Build prompt
        prompt = self._build_prompt(candidates, context)

        # Query LLM
        if self._config.provider == LLMProvider.OLLAMA:
            response = await self._query_ollama(prompt)
        elif self._config.provider == LLMProvider.OPENAI:
            response = await self._query_openai(prompt)
        else:
            return candidates, LLMDisambiguationResult(
                success=False,
                error=f"Unknown provider: {self._config.provider}",
            )

        if response is None:
            return candidates, LLMDisambiguationResult(
                success=False,
                error="LLM query failed",
            )

        # Parse response
        result = self._parse_response(response, len(candidates))

        if not result.success:
            # Return original candidates on failure
            return candidates, result

        # Reorder candidates based on ranking
        ranked_candidates: list[ParseCandidate] = []
        seen_indices: set[int] = set()

        for idx in result.ranked_indices:
            if idx < len(candidates) and idx not in seen_indices:
                ranked_candidates.append(candidates[idx])
                seen_indices.add(idx)

        # Add any candidates not in ranking
        for i, candidate in enumerate(candidates):
            if i not in seen_indices:
                ranked_candidates.append(candidate)

        return ranked_candidates, result

    async def health_check(self) -> bool:
        """Check if LLM is available.

        Returns:
            True if LLM responds, False otherwise.
        """
        if self._config.provider == LLMProvider.OLLAMA:
            try:
                timeout = aiohttp.ClientTimeout(total=5.0)
                async with aiohttp.ClientSession(timeout=timeout) as session:
                    async with session.get(
                        f"{self._config.ollama_url}/api/tags"
                    ) as response:
                        return response.status == 200
            except Exception:
                return False
        elif self._config.provider == LLMProvider.OPENAI:
            # For OpenAI, just check if API key is configured
            return bool(self._config.openai_api_key)

        return False
