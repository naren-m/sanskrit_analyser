"""Tests for LLM-based disambiguation."""

from unittest.mock import AsyncMock, patch

import pytest

from sanskrit_analyzer.disambiguation.llm import (
    LLMConfig,
    LLMDisambiguationResult,
    LLMDisambiguator,
    LLMProvider,
)
from sanskrit_analyzer.disambiguation.rules import ParseCandidate


class TestLLMConfig:
    """Tests for LLMConfig dataclass."""

    def test_defaults(self) -> None:
        """Test default configuration."""
        config = LLMConfig()
        assert config.provider == LLMProvider.OLLAMA
        assert config.model == "llama3.2"
        assert config.ollama_url == "http://localhost:11434"
        assert config.timeout == 30.0

    def test_custom_config(self) -> None:
        """Test custom configuration."""
        config = LLMConfig(
            provider=LLMProvider.OPENAI,
            model="gpt-4",
            openai_api_key="test-key",
        )
        assert config.provider == LLMProvider.OPENAI
        assert config.model == "gpt-4"


class TestLLMDisambiguationResult:
    """Tests for LLMDisambiguationResult dataclass."""

    def test_success_result(self) -> None:
        """Test successful result."""
        result = LLMDisambiguationResult(
            success=True,
            ranked_indices=[0, 2, 1],
            explanation="Test explanation",
        )
        assert result.success is True
        assert result.ranked_indices == [0, 2, 1]
        assert result.explanation == "Test explanation"

    def test_failure_result(self) -> None:
        """Test failure result."""
        result = LLMDisambiguationResult(
            success=False,
            error="Connection failed",
        )
        assert result.success is False
        assert result.error == "Connection failed"


class TestLLMDisambiguator:
    """Tests for LLMDisambiguator class."""

    @pytest.fixture
    def disambiguator(self) -> LLMDisambiguator:
        """Create a disambiguator instance."""
        return LLMDisambiguator()

    @pytest.fixture
    def candidates(self) -> list[ParseCandidate]:
        """Create test candidates."""
        return [
            ParseCandidate(
                index=0,
                segments=[
                    {
                        "surface": "gacchati",
                        "lemma": "gam",
                        "pos": "verb",
                        "morphology": {"person": "3", "number": "singular"},
                    }
                ],
                confidence=0.9,
            ),
            ParseCandidate(
                index=1,
                segments=[
                    {
                        "surface": "gacchati",
                        "lemma": "gacch",
                        "pos": "noun",
                        "morphology": {"case": "locative"},
                    }
                ],
                confidence=0.7,
            ),
        ]

    def test_init(self, disambiguator: LLMDisambiguator) -> None:
        """Test initialization."""
        assert disambiguator.enabled is True

    def test_enable_disable(self, disambiguator: LLMDisambiguator) -> None:
        """Test enabling and disabling."""
        disambiguator.enabled = False
        assert disambiguator.enabled is False

        disambiguator.enabled = True
        assert disambiguator.enabled is True

    def test_build_prompt(
        self, disambiguator: LLMDisambiguator, candidates: list[ParseCandidate]
    ) -> None:
        """Test prompt building."""
        prompt = disambiguator._build_prompt(candidates)

        assert "Candidate 0" in prompt
        assert "Candidate 1" in prompt
        assert "gam" in prompt
        assert "verb" in prompt
        assert "Confidence" in prompt

    def test_build_prompt_with_context(
        self, disambiguator: LLMDisambiguator, candidates: list[ParseCandidate]
    ) -> None:
        """Test prompt building with context."""
        context = {
            "previous_sentence": "rāmo vanam agacchat",
            "topic": "Ramayana narrative",
        }
        prompt = disambiguator._build_prompt(candidates, context)

        assert "Previous:" in prompt
        assert "rāmo vanam agacchat" in prompt
        assert "Topic:" in prompt

    def test_parse_response_success(
        self, disambiguator: LLMDisambiguator
    ) -> None:
        """Test parsing successful response."""
        response = '''
        Here is my analysis:
        {
            "ranking": [1, 0],
            "explanation": "The verb form is more likely given context."
        }
        '''
        result = disambiguator._parse_response(response, 2)

        assert result.success is True
        assert result.ranked_indices == [1, 0]
        assert "verb form" in result.explanation

    def test_parse_response_invalid_json(
        self, disambiguator: LLMDisambiguator
    ) -> None:
        """Test parsing invalid JSON response."""
        response = "This is not JSON at all"
        result = disambiguator._parse_response(response, 2)

        assert result.success is False
        assert "No JSON found" in result.error

    def test_parse_response_invalid_indices(
        self, disambiguator: LLMDisambiguator
    ) -> None:
        """Test parsing response with invalid indices."""
        response = '{"ranking": [5, 10], "explanation": "test"}'
        result = disambiguator._parse_response(response, 2)

        assert result.success is False
        assert "No valid indices" in result.error

    def test_parse_response_partial_valid(
        self, disambiguator: LLMDisambiguator
    ) -> None:
        """Test parsing response with some valid indices."""
        response = '{"ranking": [0, 99, 1], "explanation": "test"}'
        result = disambiguator._parse_response(response, 2)

        assert result.success is True
        assert result.ranked_indices == [0, 1]

    @pytest.mark.asyncio
    async def test_disambiguate_disabled(
        self, disambiguator: LLMDisambiguator, candidates: list[ParseCandidate]
    ) -> None:
        """Test disambiguation when disabled."""
        disambiguator.enabled = False
        result_candidates, result = await disambiguator.disambiguate(candidates)

        assert result_candidates == candidates
        assert result.success is False
        assert "disabled" in result.error

    @pytest.mark.asyncio
    async def test_disambiguate_single_candidate(
        self, disambiguator: LLMDisambiguator
    ) -> None:
        """Test disambiguation with single candidate."""
        candidates = [
            ParseCandidate(index=0, segments=[], confidence=0.9)
        ]
        result_candidates, result = await disambiguator.disambiguate(candidates)

        assert len(result_candidates) == 1
        assert result.success is True

    @pytest.mark.asyncio
    async def test_disambiguate_ollama_success(
        self, disambiguator: LLMDisambiguator, candidates: list[ParseCandidate]
    ) -> None:
        """Test successful Ollama disambiguation."""
        mock_response = '{"ranking": [1, 0], "explanation": "Better fit"}'

        async def mock_query(prompt: str) -> str:
            return mock_response

        disambiguator._query_ollama = mock_query  # type: ignore

        result_candidates, result = await disambiguator.disambiguate(candidates)

        assert result.success is True
        assert result_candidates[0].index == 1  # Reordered
        assert result_candidates[1].index == 0

    @pytest.mark.asyncio
    async def test_disambiguate_ollama_failure(
        self, disambiguator: LLMDisambiguator, candidates: list[ParseCandidate]
    ) -> None:
        """Test Ollama query failure."""

        async def mock_query(prompt: str) -> None:
            return None

        disambiguator._query_ollama = mock_query  # type: ignore

        result_candidates, result = await disambiguator.disambiguate(candidates)

        # Should return original candidates on failure
        assert result_candidates == candidates
        assert result.success is False
        assert "failed" in result.error

    @pytest.mark.asyncio
    async def test_disambiguate_openai(
        self, candidates: list[ParseCandidate]
    ) -> None:
        """Test OpenAI disambiguation."""
        config = LLMConfig(
            provider=LLMProvider.OPENAI,
            model="gpt-4",
            openai_api_key="test-key",
        )
        disambiguator = LLMDisambiguator(config)

        mock_response = '{"ranking": [0, 1], "explanation": "First is best"}'

        async def mock_query(prompt: str) -> str:
            return mock_response

        disambiguator._query_openai = mock_query  # type: ignore

        result_candidates, result = await disambiguator.disambiguate(candidates)

        assert result.success is True

    @pytest.mark.asyncio
    async def test_health_check_ollama(
        self, disambiguator: LLMDisambiguator
    ) -> None:
        """Test Ollama health check."""
        # Without mocking, this will fail (no Ollama running)
        result = await disambiguator.health_check()
        # Result depends on whether Ollama is running
        assert isinstance(result, bool)

    @pytest.mark.asyncio
    async def test_health_check_openai_no_key(self) -> None:
        """Test OpenAI health check without API key."""
        config = LLMConfig(provider=LLMProvider.OPENAI)
        disambiguator = LLMDisambiguator(config)

        result = await disambiguator.health_check()
        assert result is False

    @pytest.mark.asyncio
    async def test_health_check_openai_with_key(self) -> None:
        """Test OpenAI health check with API key."""
        config = LLMConfig(
            provider=LLMProvider.OPENAI,
            openai_api_key="test-key",
        )
        disambiguator = LLMDisambiguator(config)

        result = await disambiguator.health_check()
        assert result is True  # Just checks key exists

    @pytest.mark.asyncio
    async def test_disambiguate_preserves_unranked(
        self, candidates: list[ParseCandidate]
    ) -> None:
        """Test that unranked candidates are preserved."""
        # Add a third candidate
        candidates.append(
            ParseCandidate(index=2, segments=[], confidence=0.5)
        )

        disambiguator = LLMDisambiguator()

        # Mock response only ranks 2 candidates
        mock_response = '{"ranking": [0], "explanation": "Only first"}'

        async def mock_query(prompt: str) -> str:
            return mock_response

        disambiguator._query_ollama = mock_query  # type: ignore

        result_candidates, result = await disambiguator.disambiguate(candidates)

        # All 3 candidates should be in result
        assert len(result_candidates) == 3
        # First should be the ranked one
        assert result_candidates[0].index == 0
        # Others should follow
        indices = [c.index for c in result_candidates]
        assert set(indices) == {0, 1, 2}

    def test_parse_response_json_error(
        self, disambiguator: LLMDisambiguator
    ) -> None:
        """Test handling malformed JSON."""
        response = '{"ranking": [0, 1], "explanation": }'  # Invalid JSON
        result = disambiguator._parse_response(response, 2)

        assert result.success is False
        assert "JSON" in result.error or "parse" in result.error.lower()
