"""Tests for main Analyzer class."""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from sanskrit_analyzer.analyzer import Analyzer, CorpusStats
from sanskrit_analyzer.config import AnalysisMode, Config
from sanskrit_analyzer.engines.base import EngineResult, Segment
from sanskrit_analyzer.engines.ensemble import EnsembleResult, MergedSegment
from sanskrit_analyzer.models.tree import AnalysisTree, CacheTier


class TestAnalyzerInit:
    """Tests for Analyzer initialization."""

    def test_default_init(self) -> None:
        """Test default initialization."""
        analyzer = Analyzer()
        assert analyzer._config is not None
        assert analyzer._initialized is False

    def test_with_config(self) -> None:
        """Test initialization with config."""
        config = Config()
        config.default_mode = AnalysisMode.EDUCATIONAL
        analyzer = Analyzer(config)
        assert analyzer.config.default_mode == AnalysisMode.EDUCATIONAL

    def test_from_config_missing_file(self, tmp_path: Path) -> None:
        """Test from_config with missing file uses defaults."""
        analyzer = Analyzer.from_config(tmp_path / "missing.yaml")
        assert analyzer._config is not None

    def test_from_config_valid_file(self, tmp_path: Path) -> None:
        """Test from_config with valid file."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text("""
default_mode: educational
engines:
  vidyut: true
  dharmamitra: false
""")
        analyzer = Analyzer.from_config(config_file)
        assert analyzer.config.default_mode == AnalysisMode.EDUCATIONAL
        assert analyzer.config.engines.dharmamitra is False


class TestAnalyzerAnalyze:
    """Tests for Analyzer.analyze() method."""

    @pytest.fixture
    def analyzer(self) -> Analyzer:
        """Create analyzer with mocked components."""
        config = Config()
        # Disable all engines to speed up tests
        config.engines.vidyut = False
        config.engines.dharmamitra = False
        config.engines.heritage = False
        config.cache.redis_enabled = False
        config.cache.sqlite_enabled = False
        config.disambiguation.llm_enabled = False
        return Analyzer(config)

    @pytest.fixture
    def mock_ensemble_result(self) -> EnsembleResult:
        """Create mock ensemble result."""
        return EnsembleResult(
            segments=[
                MergedSegment(
                    surface="rAmaH",
                    lemma="rAma",
                    morphology="noun.masculine.singular.nominative",
                    confidence=0.9,
                    pos="noun",
                    meanings=["Rama"],
                    engine_votes={"test": 0.9},
                    agreement_score=0.9,
                ),
                MergedSegment(
                    surface="gacCati",
                    lemma="gam",
                    morphology="verb.third.singular.present",
                    confidence=0.95,
                    pos="verb",
                    meanings=["goes"],
                    engine_votes={"test": 0.95},
                    agreement_score=0.95,
                ),
            ],
            engine_results={
                "test": EngineResult(
                    engine="test",
                    segments=[
                        Segment(surface="rAmaH", lemma="rAma", confidence=0.9, pos="noun"),
                        Segment(surface="gacCati", lemma="gam", confidence=0.95, pos="verb"),
                    ],
                    confidence=0.92,
                ),
            },
            overall_confidence=0.92,
            agreement_level="high",
        )

    @pytest.mark.asyncio
    async def test_analyze_basic(
        self,
        analyzer: Analyzer,
        mock_ensemble_result: EnsembleResult,
    ) -> None:
        """Test basic analysis."""
        # Mock the ensemble
        analyzer._initialized = True
        analyzer._ensemble = MagicMock()
        analyzer._ensemble.analyze = AsyncMock(return_value=mock_ensemble_result)
        analyzer._tree_builder = MagicMock()
        analyzer._cache = None
        analyzer._disambiguation = None

        # Create a mock tree
        from sanskrit_analyzer.models.tree import ConfidenceMetrics, ParseTree

        mock_tree = AnalysisTree(
            sentence_id="test",
            original_text="rāmaḥ gacchati",
            normalized_slp1="rAmaH gacCati",
            scripts=MagicMock(),
            parse_forest=[ParseTree(parse_id="p1", confidence=0.9)],
            confidence=ConfidenceMetrics(overall=0.9, engine_agreement=0.9),
        )
        analyzer._tree_builder.build = MagicMock(return_value=mock_tree)

        result = await analyzer.analyze("rāmaḥ gacchati")

        assert result is not None
        assert result.original_text == "rāmaḥ gacchati"
        analyzer._ensemble.analyze.assert_called_once()

    @pytest.mark.asyncio
    async def test_analyze_devanagari_input(
        self,
        analyzer: Analyzer,
        mock_ensemble_result: EnsembleResult,
    ) -> None:
        """Test analysis with Devanagari input."""
        analyzer._initialized = True
        analyzer._ensemble = MagicMock()
        analyzer._ensemble.analyze = AsyncMock(return_value=mock_ensemble_result)
        analyzer._tree_builder = MagicMock()
        analyzer._cache = None
        analyzer._disambiguation = None

        from sanskrit_analyzer.models.tree import ConfidenceMetrics, ParseTree

        mock_tree = AnalysisTree(
            sentence_id="test",
            original_text="रामः गच्छति",
            normalized_slp1="rAmaH gacCati",
            scripts=MagicMock(),
            parse_forest=[ParseTree(parse_id="p1", confidence=0.9)],
            confidence=ConfidenceMetrics(overall=0.9, engine_agreement=0.9),
        )
        analyzer._tree_builder.build = MagicMock(return_value=mock_tree)

        result = await analyzer.analyze("रामः गच्छति")

        assert result is not None
        # Ensemble should receive normalized SLP1
        call_args = analyzer._ensemble.analyze.call_args[0][0]
        assert call_args == "rAmaH gacCati"

    @pytest.mark.asyncio
    async def test_analyze_with_mode(
        self,
        analyzer: Analyzer,
        mock_ensemble_result: EnsembleResult,
    ) -> None:
        """Test analysis with specific mode."""
        analyzer._initialized = True
        analyzer._ensemble = MagicMock()
        analyzer._ensemble.analyze = AsyncMock(return_value=mock_ensemble_result)
        analyzer._tree_builder = MagicMock()
        analyzer._cache = None
        analyzer._disambiguation = None

        from sanskrit_analyzer.models.tree import ConfidenceMetrics, ParseTree

        mock_tree = AnalysisTree(
            sentence_id="test",
            original_text="test",
            normalized_slp1="test",
            scripts=MagicMock(),
            parse_forest=[ParseTree(parse_id="p1", confidence=0.9)],
            confidence=ConfidenceMetrics(overall=0.9, engine_agreement=0.9),
        )
        analyzer._tree_builder.build = MagicMock(return_value=mock_tree)

        result = await analyzer.analyze("test", mode=AnalysisMode.EDUCATIONAL)

        assert result is not None
        # Mode should be passed to tree builder
        call_args = analyzer._tree_builder.build.call_args
        # Mode is 4th positional arg (index 3)
        assert call_args[0][3] == "educational"

    @pytest.mark.asyncio
    async def test_analyze_cache_hit(self, analyzer: Analyzer) -> None:
        """Test cache hit scenario."""
        analyzer._initialized = True
        analyzer._ensemble = MagicMock()
        analyzer._tree_builder = MagicMock()
        analyzer._disambiguation = None

        # Mock cache with hit
        analyzer._cache = MagicMock()
        analyzer._cache._memory = MagicMock()
        analyzer._cache._memory.make_key = MagicMock(return_value="test_key")
        analyzer._cache.get = AsyncMock(return_value={
            "sentence_id": "cached",
            "confidence": {"overall": 0.9, "engine_agreement": 0.9},
        })

        result = await analyzer.analyze("test")

        assert result is not None
        assert result.cached_at == CacheTier.MEMORY
        # Ensemble should NOT be called on cache hit
        analyzer._ensemble.analyze.assert_not_called()

    @pytest.mark.asyncio
    async def test_analyze_bypass_cache(
        self,
        analyzer: Analyzer,
        mock_ensemble_result: EnsembleResult,
    ) -> None:
        """Test bypassing cache."""
        analyzer._initialized = True
        analyzer._ensemble = MagicMock()
        analyzer._ensemble.analyze = AsyncMock(return_value=mock_ensemble_result)
        analyzer._tree_builder = MagicMock()
        analyzer._disambiguation = None

        from sanskrit_analyzer.models.tree import ConfidenceMetrics, ParseTree

        mock_tree = AnalysisTree(
            sentence_id="test",
            original_text="test",
            normalized_slp1="test",
            scripts=MagicMock(),
            parse_forest=[ParseTree(parse_id="p1", confidence=0.9)],
            confidence=ConfidenceMetrics(overall=0.9, engine_agreement=0.9),
        )
        analyzer._tree_builder.build = MagicMock(return_value=mock_tree)

        # Mock cache
        analyzer._cache = MagicMock()
        analyzer._cache._memory = MagicMock()
        analyzer._cache._memory.make_key = MagicMock(return_value="test_key")
        analyzer._cache.get = AsyncMock(return_value={"cached": True})
        analyzer._cache.set = AsyncMock()

        result = await analyzer.analyze("test", bypass_cache=True)

        assert result is not None
        # Ensemble should be called despite cache having data
        analyzer._ensemble.analyze.assert_called_once()


class TestAnalyzerBatch:
    """Tests for batch analysis."""

    @pytest.fixture
    def analyzer(self) -> Analyzer:
        """Create analyzer with minimal config."""
        config = Config()
        config.engines.vidyut = False
        config.engines.dharmamitra = False
        config.engines.heritage = False
        config.cache.redis_enabled = False
        config.cache.sqlite_enabled = False
        config.disambiguation.llm_enabled = False
        return Analyzer(config)

    @pytest.mark.asyncio
    async def test_analyze_batch(self, analyzer: Analyzer) -> None:
        """Test batch analysis."""
        analyzer._initialized = True
        analyzer._ensemble = MagicMock()
        analyzer._cache = None
        analyzer._disambiguation = None

        # Mock analyze
        call_count = 0

        async def mock_analyze(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            from sanskrit_analyzer.models.tree import ConfidenceMetrics, ParseTree

            return AnalysisTree(
                sentence_id=f"test_{call_count}",
                original_text=args[0] if args else "test",
                normalized_slp1="test",
                scripts=MagicMock(),
                parse_forest=[],
                confidence=ConfidenceMetrics(overall=0.9, engine_agreement=0.9),
            )

        analyzer.analyze = mock_analyze  # type: ignore

        results = await analyzer.analyze_batch(["text1", "text2", "text3"])

        assert len(results) == 3
        assert call_count == 3


class TestAnalyzerHealthCheck:
    """Tests for health check functionality."""

    @pytest.fixture
    def analyzer(self) -> Analyzer:
        """Create analyzer."""
        config = Config()
        config.engines.vidyut = False
        config.engines.dharmamitra = False
        config.engines.heritage = False
        return Analyzer(config)

    @pytest.mark.asyncio
    async def test_health_check_basic(self, analyzer: Analyzer) -> None:
        """Test basic health check."""
        analyzer._initialized = True
        analyzer._ensemble = MagicMock()
        analyzer._ensemble._engines = []
        analyzer._disambiguation = MagicMock()
        analyzer._disambiguation.health_check = AsyncMock(return_value={"rules": True})
        analyzer._cache = MagicMock()
        analyzer._cache._memory = MagicMock()
        analyzer._cache._redis = None
        analyzer._cache._sqlite = MagicMock()

        health = await analyzer.health_check()

        assert "disambiguation_rules" in health
        assert health["cache_memory"] is True


class TestAnalyzerStats:
    """Tests for corpus statistics."""

    @pytest.fixture
    def analyzer(self) -> Analyzer:
        """Create analyzer."""
        return Analyzer()

    @pytest.mark.asyncio
    async def test_get_corpus_stats(self, analyzer: Analyzer) -> None:
        """Test getting corpus stats."""
        analyzer._initialized = True

        # Set up cache mocks with proper structure
        analyzer._cache = MagicMock()
        analyzer._cache.stats = MagicMock()
        analyzer._cache._memory = MagicMock()
        analyzer._cache._memory.stats = MagicMock()
        analyzer._cache._memory.stats.size = 100
        analyzer._cache._memory.stats.hit_rate = 0.75
        analyzer._cache._sqlite = MagicMock()
        analyzer._cache._sqlite.count = MagicMock(return_value=500)

        stats = await analyzer.get_corpus_stats()

        assert isinstance(stats, CorpusStats)
        assert stats.memory_entries == 100
        assert stats.cache_hit_rate == 0.75
        assert stats.sqlite_entries == 500


class TestAnalyzerCacheKey:
    """Tests for cache key generation."""

    def test_make_cache_key(self) -> None:
        """Test cache key generation."""
        analyzer = Analyzer()
        analyzer._cache = MagicMock()
        analyzer._cache._memory = MagicMock()
        analyzer._cache._memory.make_key = MagicMock(return_value="test_key")

        key = analyzer._make_cache_key("rAmaH", "production")

        assert key == "test_key"
        analyzer._cache._memory.make_key.assert_called_once_with("rAmaH", "production")

    def test_make_cache_key_no_cache(self) -> None:
        """Test cache key generation without cache."""
        analyzer = Analyzer()
        analyzer._cache = None

        key = analyzer._make_cache_key("rAmaH", "production")

        assert isinstance(key, str)
        assert len(key) == 32  # SHA256 truncated


class TestAnalyzerEngines:
    """Tests for engine management."""

    def test_get_available_engines_empty(self) -> None:
        """Test getting engines when not initialized."""
        analyzer = Analyzer()
        engines = analyzer.get_available_engines()
        assert engines == []

    def test_get_available_engines(self) -> None:
        """Test getting available engines."""
        analyzer = Analyzer()
        analyzer._ensemble = MagicMock()
        analyzer._ensemble.available_engines = ["vidyut", "dharmamitra"]

        engines = analyzer.get_available_engines()

        assert engines == ["vidyut", "dharmamitra"]


class TestAnalyzerClearCache:
    """Tests for cache clearing."""

    @pytest.mark.asyncio
    async def test_clear_cache_all(self) -> None:
        """Test clearing all cache tiers."""
        analyzer = Analyzer()
        analyzer._cache = MagicMock()
        analyzer._cache._memory = MagicMock()
        analyzer._cache._redis = None
        analyzer._cache._sqlite = None

        await analyzer.clear_cache()

        analyzer._cache._memory.clear.assert_called_once()

    @pytest.mark.asyncio
    async def test_clear_cache_specific_tier(self) -> None:
        """Test clearing specific cache tier."""
        analyzer = Analyzer()
        analyzer._cache = MagicMock()
        analyzer._cache._memory = MagicMock()
        analyzer._cache._redis = None

        await analyzer.clear_cache(tier="memory")

        analyzer._cache._memory.clear.assert_called_once()

    @pytest.mark.asyncio
    async def test_clear_cache_no_cache(self) -> None:
        """Test clearing when no cache configured."""
        analyzer = Analyzer()
        analyzer._cache = None

        # Should not raise
        await analyzer.clear_cache()
