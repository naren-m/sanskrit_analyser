"""Tests for Heritage Engine client."""

from unittest.mock import AsyncMock, patch

import pytest

from sanskrit_analyzer.engines.heritage_engine import HeritageEngine


class TestHeritageEngine:
    """Tests for HeritageEngine class."""

    @pytest.fixture
    def engine(self) -> HeritageEngine:
        """Create a HeritageEngine instance."""
        return HeritageEngine(use_local=False)  # Use public URL for tests

    def test_engine_name(self, engine: HeritageEngine) -> None:
        """Test engine name property."""
        assert engine.name == "heritage"

    def test_engine_weight(self, engine: HeritageEngine) -> None:
        """Test engine weight property."""
        assert engine.weight == 0.25

    def test_is_available(self, engine: HeritageEngine) -> None:
        """Test that engine is marked as available."""
        assert engine.is_available is True

    def test_normalize_to_slp1(self, engine: HeritageEngine) -> None:
        """Test script normalization."""
        # Test Devanagari to SLP1
        result = engine._normalize_to_slp1("राम")
        assert result == "rAma"

    def test_build_url(self, engine: HeritageEngine) -> None:
        """Test URL building."""
        url = engine._build_url("https://example.com", "gam")
        assert "example.com" in url
        assert "gam" in url

    @pytest.mark.asyncio
    async def test_analyze_returns_engine_result(self, engine: HeritageEngine) -> None:
        """Test that analyze returns proper EngineResult."""
        with patch.object(
            engine, "_query_heritage", new_callable=AsyncMock
        ) as mock_query:
            mock_query.return_value = "<html><body>test</body></html>"

            result = await engine.analyze("gacchati")

            assert result.engine == "heritage"
            assert isinstance(result.segments, list)

    @pytest.mark.asyncio
    async def test_analyze_empty_input(self, engine: HeritageEngine) -> None:
        """Test analysis of empty input."""
        result = await engine.analyze("")

        assert result.engine == "heritage"
        assert len(result.segments) == 0
        assert result.confidence == 0.0

    @pytest.mark.asyncio
    async def test_analyze_handles_connection_error(
        self, engine: HeritageEngine
    ) -> None:
        """Test that connection errors are handled gracefully."""
        with patch.object(
            engine, "_query_heritage", new_callable=AsyncMock
        ) as mock_query:
            mock_query.return_value = None

            result = await engine.analyze("gacchati")

            assert result.engine == "heritage"
            assert result.error is not None
            assert "unreachable" in result.error.lower()

    @pytest.mark.asyncio
    async def test_analyze_with_valid_response(self, engine: HeritageEngine) -> None:
        """Test analysis with mocked valid response."""
        with patch.object(
            engine, "_query_heritage", new_callable=AsyncMock
        ) as mock_query:
            # Simulate a valid HTML response with table structure
            mock_query.return_value = """
            <html>
            <body>
            <table><td>gacchati</td></table>
            </body>
            </html>
            """

            result = await engine.analyze("gacchati")

            assert result.success
            assert len(result.segments) >= 1

    @pytest.mark.asyncio
    async def test_fallback_to_public(self, engine: HeritageEngine) -> None:
        """Test fallback from local to public URL."""
        engine_with_local = HeritageEngine(use_local=True)

        with patch.object(
            engine_with_local, "_query_heritage", new_callable=AsyncMock
        ) as mock_query:
            # First call (local) returns None, second call (public) returns HTML
            mock_query.side_effect = [None, "<html><td>test</td></html>"]

            result = await engine_with_local.analyze("gam")

            # Should have tried both URLs
            assert mock_query.call_count == 2
            assert result.success

    @pytest.mark.asyncio
    async def test_health_check_success(self, engine: HeritageEngine) -> None:
        """Test health check when engine responds."""
        with patch.object(
            engine, "_query_heritage", new_callable=AsyncMock
        ) as mock_query:
            mock_query.return_value = "<html>OK</html>"

            result = await engine.health_check()

            assert result is True

    @pytest.mark.asyncio
    async def test_health_check_failure(self, engine: HeritageEngine) -> None:
        """Test health check when engine doesn't respond."""
        with patch.object(
            engine, "_query_heritage", new_callable=AsyncMock
        ) as mock_query:
            mock_query.return_value = None

            result = await engine.health_check()

            assert result is False
