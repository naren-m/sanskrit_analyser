"""Tests for main Analyzer class."""

import json
import re
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from sanskrit_analyzer.analyzer import Analyzer, CorpusStats
from sanskrit_analyzer.config import AnalysisMode, Config
from sanskrit_analyzer.disambiguation.llm import LLMDisambiguator
from sanskrit_analyzer.engines.base import EngineResult, Segment
from sanskrit_analyzer.engines.runner import AnalyzedSegment, EngineRunResult
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
""")
        analyzer = Analyzer.from_config(config_file)
        assert analyzer.config.default_mode == AnalysisMode.EDUCATIONAL


class TestAnalyzerAnalyze:
    """Tests for Analyzer.analyze() method."""

    @pytest.fixture
    def analyzer(self) -> Analyzer:
        """Create analyzer with mocked components."""
        config = Config()
        # Disable all engines to speed up tests
        config.engines.vidyut = False
        config.cache.redis_enabled = False
        config.cache.sqlite_enabled = False
        config.disambiguation.llm_enabled = False
        return Analyzer(config)

    @pytest.fixture
    def mock_run_result(self) -> EngineRunResult:
        """Create mock runner result."""
        return EngineRunResult(
            segments=[
                AnalyzedSegment(
                    surface="rAmaH",
                    lemma="rAma",
                    morphology="noun.masculine.singular.nominative",
                    confidence=0.9,
                    pos="noun",
                    meanings=["Rama"],
                    engine_votes={"test": 0.9},
                    agreement_score=0.9,
                ),
                AnalyzedSegment(
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
        )

    @pytest.mark.asyncio
    async def test_analyze_basic(
        self,
        analyzer: Analyzer,
        mock_run_result: EngineRunResult,
    ) -> None:
        """Test basic analysis."""
        # Mock the runner
        analyzer._initialized = True
        analyzer._runner = MagicMock()
        analyzer._runner.analyze = AsyncMock(return_value=mock_run_result)
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
        analyzer._runner.analyze.assert_called_once()

    def _make_mock_tree(self) -> AnalysisTree:
        from sanskrit_analyzer.models.tree import ConfidenceMetrics, ParseTree

        return AnalysisTree(
            sentence_id="test",
            original_text="rāmaḥ gacchati",
            normalized_slp1="rAmaH gacCati",
            scripts=MagicMock(),
            parse_forest=[ParseTree(parse_id="p1", confidence=0.9)],
            confidence=ConfidenceMetrics(overall=0.9, engine_agreement=0.9),
        )

    @pytest.mark.asyncio
    async def test_split_validator_skipped_for_non_vidyut_segments(
        self,
        analyzer: Analyzer,
        mock_run_result: EngineRunResult,
    ) -> None:
        """Validator must not override segmentation from non-vidyut engines.

        The split validator rescores *vidyut* splits against a small curated
        vocabulary. When segments come from another engine (e.g. local ByT5,
        whose neural segmentation is already high quality), re-splitting them
        against the 99-word vocab corrupts correct lemmas (observed live:
        'yatna' -> 'yat'+'na'). mock_run_result's engine_results only
        contain the key "test" — no vidyut — so the runner path must be used.
        """
        analyzer._initialized = True
        analyzer._runner = MagicMock()
        analyzer._runner.analyze = AsyncMock(return_value=mock_run_result)
        analyzer._tree_builder = MagicMock()
        analyzer._cache = None
        analyzer._disambiguation = None
        analyzer._split_validator = MagicMock()

        mock_tree = self._make_mock_tree()
        analyzer._tree_builder.build = MagicMock(return_value=mock_tree)
        analyzer._tree_builder.build_from_segments = MagicMock(return_value=mock_tree)

        await analyzer.analyze("rāmaḥ gacchati")

        analyzer._split_validator.rank_candidates.assert_not_called()
        analyzer._tree_builder.build_from_segments.assert_not_called()
        analyzer._tree_builder.build.assert_called_once()

    @pytest.mark.asyncio
    async def test_split_validator_used_for_vidyut_segments(
        self,
        analyzer: Analyzer,
        mock_run_result: EngineRunResult,
    ) -> None:
        """Validator path stays active when vidyut produced the segments."""
        vidyut_segments = [
            Segment(surface="rAmaH", lemma="rAma", confidence=0.9, pos="noun"),
            Segment(surface="gacCati", lemma="gam", confidence=0.95, pos="verb"),
        ]
        mock_run_result.engine_results["vidyut"] = EngineResult(
            engine="vidyut",
            segments=vidyut_segments,
            confidence=0.9,
        )

        analyzer._initialized = True
        analyzer._runner = MagicMock()
        analyzer._runner.analyze = AsyncMock(return_value=mock_run_result)
        analyzer._tree_builder = MagicMock()
        analyzer._cache = None
        analyzer._disambiguation = None
        analyzer._split_validator = MagicMock()
        analyzer._split_validator.rank_candidates = MagicMock(
            return_value=[(0.0, vidyut_segments)]
        )

        mock_tree = self._make_mock_tree()
        analyzer._tree_builder.build = MagicMock(return_value=mock_tree)
        analyzer._tree_builder.build_from_segments = MagicMock(return_value=mock_tree)

        await analyzer.analyze("rāmaḥ gacchati")

        analyzer._split_validator.rank_candidates.assert_called_once()
        analyzer._tree_builder.build_from_segments.assert_called_once()
        analyzer._tree_builder.build.assert_not_called()

    @pytest.mark.asyncio
    async def test_vocabulary_only_fallback_is_not_confident(self) -> None:
        """No engine segments -> validator guesses from ~100 words; say so.

        With the vidyut bundle missing, 'yogaScittavfttiniroDaH' came back as
        yoga|S|citta|vftti|niroDa|H at overall confidence 1.0, labelled
        'vidyut+validator', so callers could not tell the result was a guess.
        """
        analyzer = Analyzer(Config())
        await analyzer._initialize()
        if analyzer._split_validator is None:
            pytest.skip("split validator unavailable")
        analyzer._cache = None
        analyzer._runner = MagicMock()
        analyzer._runner.analyze = AsyncMock(
            return_value=EngineRunResult(errors=["vidyut: data missing"])
        )

        tree = await analyzer.analyze("yogaScittavfttiniroDaH")

        assert tree.parse_forest, "fallback should still produce a split"
        assert tree.confidence.overall <= 0.3
        assert "vidyut+validator" not in tree.best_parse.engine_votes

    @pytest.mark.asyncio
    async def test_analyze_devanagari_input(
        self,
        analyzer: Analyzer,
        mock_run_result: EngineRunResult,
    ) -> None:
        """Test analysis with Devanagari input."""
        analyzer._initialized = True
        analyzer._runner = MagicMock()
        analyzer._runner.analyze = AsyncMock(return_value=mock_run_result)
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
        # Runner should receive normalized SLP1
        call_args = analyzer._runner.analyze.call_args[0][0]
        assert call_args == "rAmaH gacCati"

    @pytest.mark.asyncio
    async def test_analyze_with_mode(
        self,
        analyzer: Analyzer,
        mock_run_result: EngineRunResult,
    ) -> None:
        """Test analysis with specific mode."""
        analyzer._initialized = True
        analyzer._runner = MagicMock()
        analyzer._runner.analyze = AsyncMock(return_value=mock_run_result)
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
        analyzer._runner = MagicMock()
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
        # Runner should NOT be called on cache hit
        analyzer._runner.analyze.assert_not_called()

    @pytest.mark.asyncio
    async def test_analyze_bypass_cache(
        self,
        analyzer: Analyzer,
        mock_run_result: EngineRunResult,
    ) -> None:
        """Test bypassing cache."""
        analyzer._initialized = True
        analyzer._runner = MagicMock()
        analyzer._runner.analyze = AsyncMock(return_value=mock_run_result)
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
        # Runner should be called despite cache having data
        analyzer._runner.analyze.assert_called_once()


class TestDisambiguationWiring:
    """Analyzer.analyze with config.disambiguation.enabled on and off.

    Before the wiring, tree_builder emitted exactly one parse, so the
    ``len(parse_forest) > 1`` gate in _run_pipeline never passed and the
    pipeline built in _initialize never ran. With the flag on, the split
    validator's runner-up splits become the forest the pipeline ranks.
    """

    # (row id, text, disambiguation overrides, expectations)
    # parses: "1" or ">1" (full forest). stage: disambiguation_stage.
    # pick: "validator" = what validate_and_rescore alone returns;
    #       "llm-last" = the validator's lowest-ranked parse, which the fake
    #       LLM (it reverses the order it is given) must promote.
    CASES = [
        # Default config must equal pre-wiring behaviour.
        ("default-off-single-parse", "satyavAkyo", {},
         {"parses": "1", "stage": None, "pick": "validator"}),
        # 5 validator candidates -> forest; rules resolve (top conf >= 0.95).
        ("on-rules-resolve-forest", "satyavAkyo", {"enabled": True},
         {"parses": ">1", "stage": "rules"}),
        # Indeclinables short-circuit in the validator: nothing to rank.
        ("on-indeclinable-stays-single", "ca", {"enabled": True},
         {"parses": "1", "stage": None, "pick": "validator"}),
        # Vocabulary-only fallback caps confidence at 0.3 so, with rules off,
        # the LLM stage runs. Its ranking must set best_parse even though it
        # leaves confidences alone (audit H7).
        ("on-llm-ranking-drives-best-parse", "yogaScittavfttiniroDaH",
         {"enabled": True, "rules_enabled": False, "llm_enabled": True},
         {"parses": ">1", "stage": "llm", "pick": "llm-last"}),
    ]

    @staticmethod
    async def _fake_ollama(prompt: str) -> str:
        """Network-boundary fake: rank the candidates in reverse."""
        n = len(re.findall(r"^Candidate \d+:", prompt, flags=re.M))
        return json.dumps({"ranking": list(range(n - 1, -1, -1))})

    async def _analyze(self, text: str, overrides: dict) -> tuple[Analyzer, list[Segment], AnalysisTree]:
        config = Config()
        config.cache.redis_enabled = False
        config.cache.sqlite_enabled = False
        config.cache.memory_enabled = False
        for key, value in overrides.items():
            setattr(config.disambiguation, key, value)
        analyzer = Analyzer(config)
        await analyzer._initialize()
        if analyzer._split_validator is None:
            pytest.skip("split validator unavailable")
        if overrides.get("llm_enabled"):
            analyzer._runner = MagicMock()
            analyzer._runner.analyze = AsyncMock(
                return_value=EngineRunResult(errors=["vidyut: data missing"])
            )
            with patch.object(LLMDisambiguator, "_query_ollama", side_effect=self._fake_ollama):
                tree = await analyzer.analyze(text, return_all_parses=True)
            return analyzer, [], tree
        if "vidyut" not in analyzer._runner.available_engines:
            pytest.skip("vidyut data bundle not installed")
        run = await analyzer._runner.analyze(text)
        tree = await analyzer.analyze(text, return_all_parses=True)
        return analyzer, run.engine_results["vidyut"].segments, tree

    @pytest.mark.asyncio
    async def test_disambiguation_wiring_table(self) -> None:
        failures = []
        for case_id, text, overrides, want in self.CASES:
            analyzer, vidyut_segments, tree = await self._analyze(text, overrides)
            count = tree.parse_count
            if (count > 1) != (want["parses"] == ">1"):
                failures.append(f"{case_id}: {count} parses, want {want['parses']}")
                continue
            stage = tree.confidence.disambiguation_stage
            if stage != want["stage"]:
                failures.append(f"{case_id}: stage {stage!r}, want {want['stage']!r}")
            if want["stage"] and tree.best_parse is not tree.parse_forest[0]:
                failures.append(f"{case_id}: best_parse is not the pipeline's first pick")

            validator = analyzer._split_validator
            expected = None
            if want.get("pick") == "validator":
                expected = validator.validate_and_rescore(vidyut_segments, text)
            elif want.get("pick") == "llm-last":
                expected = validator.rank_candidates([], text)[:count][-1][1]
            got = [w.surface_form for w in tree.best_parse.all_words]
            if expected is not None and got != [s.surface for s in expected]:
                failures.append(f"{case_id}: picked {got}, want {[s.surface for s in expected]}")
        assert not failures, "\n".join(failures)


class TestAnalyzerBatch:
    """Tests for batch analysis."""

    @pytest.fixture
    def analyzer(self) -> Analyzer:
        """Create analyzer with minimal config."""
        config = Config()
        config.engines.vidyut = False
        config.cache.redis_enabled = False
        config.cache.sqlite_enabled = False
        config.disambiguation.llm_enabled = False
        return Analyzer(config)

    @pytest.mark.asyncio
    async def test_analyze_batch(self, analyzer: Analyzer) -> None:
        """Test batch analysis."""
        analyzer._initialized = True
        analyzer._runner = MagicMock()
        analyzer._cache = None
        analyzer._disambiguation = None

        # Mock analyze
        call_count = 0

        async def mock_analyze(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            from sanskrit_analyzer.models.tree import ConfidenceMetrics

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
        return Analyzer(config)

    @pytest.mark.asyncio
    async def test_health_check_basic(self, analyzer: Analyzer) -> None:
        """Test basic health check."""
        analyzer._initialized = True
        analyzer._runner = MagicMock()
        analyzer._runner._engines = []
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
    """The cache must not hand one request's result to a different request."""

    @pytest.mark.asyncio
    async def test_cache_serves_only_equivalent_requests(self) -> None:
        """A real memory cache, a two-parse forest, and the knobs that change output.

        Regressions pinned: a production-mode call cached the truncated forest,
        so a later return_all_parses=True got one parse; an engines= override
        wrote its result under the default key; and CACHE_SCHEMA_VERSION was
        never folded into the key, so an upgrade kept serving old results.
        """
        from sanskrit_analyzer.cache import tiered
        from sanskrit_analyzer.models.tree import ConfidenceMetrics, ParseTree

        config = Config()
        config.engines.vidyut = False
        config.cache.redis_enabled = False
        config.cache.sqlite_enabled = False
        config.disambiguation.llm_enabled = False
        analyzer = Analyzer(config)
        analyzer._initialized = True
        analyzer._disambiguation = None
        analyzer._cache = analyzer._create_cache()
        analyzer._runner = MagicMock()
        analyzer._runner.analyze = AsyncMock(return_value=EngineRunResult(segments=[]))
        analyzer._tree_builder = MagicMock()
        analyzer._tree_builder.build = MagicMock(side_effect=lambda *a, **k: AnalysisTree(
            sentence_id="s",
            original_text="rAmaH",
            normalized_slp1="rAmaH",
            scripts=MagicMock(),
            parse_forest=[ParseTree(parse_id="p1", confidence=0.9),
                          ParseTree(parse_id="p2", confidence=0.5)],
            confidence=ConfidenceMetrics(overall=0.9, engine_agreement=0.9),
        ))

        first = await analyzer.analyze("rAmaH", mode=AnalysisMode.PRODUCTION)
        full = await analyzer.analyze("rAmaH", mode=AnalysisMode.PRODUCTION,
                                      return_all_parses=True)
        await analyzer.analyze("rAmaH", engines=["local_byt5"])
        again = await analyzer.analyze("rAmaH", return_all_parses=True)

        failures = []
        if len(first.parse_forest) != 1:
            failures.append(f"production call not truncated: {len(first.parse_forest)}")
        if len(full.parse_forest) != 2:
            failures.append(f"cache served truncated forest: {len(full.parse_forest)}")
        if analyzer._runner.analyze.await_count != 2:
            failures.append(f"runner calls {analyzer._runner.analyze.await_count}, "
                            "want 2 (first miss + engines override)")
        if again.cached_at is None:
            failures.append("default request after engines override missed the cache")
        key = analyzer._cache.make_key("rAmaH", "production")
        with patch.object(tiered, "CACHE_SCHEMA_VERSION", tiered.CACHE_SCHEMA_VERSION + 1):
            if analyzer._cache.make_key("rAmaH", "production") == key:
                failures.append("schema version bump did not change the key")
        assert not failures, failures


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
        analyzer._runner = MagicMock()
        analyzer._runner.available_engines = ["vidyut", "local_byt5"]

        engines = analyzer.get_available_engines()

        assert engines == ["vidyut", "local_byt5"]


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
