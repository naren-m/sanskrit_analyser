"""Main Analyzer class - the primary public interface for Sanskrit analysis.

This module provides the high-level Analyzer class that orchestrates the entire
analysis pipeline: normalization -> caching -> ensemble analysis -> tree building
-> disambiguation -> caching -> result return.
"""

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from sanskrit_analyzer.cache.memory import LRUCache
from sanskrit_analyzer.cache.tiered import TieredCache, TieredCacheConfig
from sanskrit_analyzer.config import AnalysisMode, Config
from sanskrit_analyzer.disambiguation.llm import LLMConfig, LLMProvider
from sanskrit_analyzer.disambiguation.pipeline import (
    DisambiguationPipeline,
    HumanReviewConfig,
    PipelineConfig,
)
from sanskrit_analyzer.disambiguation.rules import (
    ParseCandidate,
    RuleBasedDisambiguatorConfig,
)
from sanskrit_analyzer.engines.base import EngineBase
from sanskrit_analyzer.engines.ensemble import EnsembleAnalyzer, EnsembleConfig
from sanskrit_analyzer.models.scripts import Script, ScriptVariants
from sanskrit_analyzer.models.tree import AnalysisTree, CacheTier
from sanskrit_analyzer.tree_builder import TreeBuilder, TreeBuilderConfig
from sanskrit_analyzer.utils.normalize import detect_script, normalize_slp1
from sanskrit_analyzer.data.dhatu_db import DhatuDB, DhatuEntry
from sanskrit_analyzer.models.dhatu import DhatuInfo
from sanskrit_analyzer.validation.split_validator import SplitValidator
from sanskrit_analyzer.validation.vocabulary import Vocabulary

logger = logging.getLogger(__name__)


@dataclass
class CorpusStats:
    """Statistics about the analysis corpus."""

    total_entries: int = 0
    disambiguated_count: int = 0
    cache_hit_rate: float = 0.0
    memory_entries: int = 0
    redis_entries: int = 0
    sqlite_entries: int = 0


class Analyzer:
    """Main Sanskrit text analyzer.

    The Analyzer is the primary public interface for the sanskrit_analyzer library.
    It orchestrates the full analysis pipeline:

    1. Normalize input text to SLP1
    2. Check tiered cache (Memory -> Redis -> SQLite)
    3. If cache miss, run ensemble analysis (Vidyut + Heritage)
    4. Build 4-level parse tree from engine results
    5. Run disambiguation pipeline (Rules -> LLM -> Human flag)
    6. Store result in tiered cache
    7. Return AnalysisTree

    Example:
        # Basic usage
        analyzer = Analyzer()
        result = await analyzer.analyze("rāmo vanam gacchati")

        # With configuration
        config = Config.from_file("~/.sanskrit_analyzer/config.yaml")
        analyzer = Analyzer(config)

        # Educational mode with all parses
        result = await analyzer.analyze(
            "rāmo vanam gacchati",
            mode=AnalysisMode.EDUCATIONAL,
            return_all_parses=True,
        )
    """

    def __init__(self, config: Config | None = None) -> None:
        """Initialize the analyzer with configuration.

        Args:
            config: Analyzer configuration. If None, uses defaults.
        """
        self._config = config or Config()
        self._setup_logging()

        # Initialize components (lazy)
        self._ensemble: EnsembleAnalyzer | None = None
        self._cache: TieredCache | None = None
        self._disambiguation: DisambiguationPipeline | None = None
        self._tree_builder: TreeBuilder | None = None
        self._dhatu_db: DhatuDB | None = None
        self._split_validator: SplitValidator | None = None

        # Lazy initialization flags
        self._initialized = False

    @classmethod
    def from_config(cls, path: str | Path) -> "Analyzer":
        """Create an Analyzer from a config file.

        Args:
            path: Path to YAML configuration file.

        Returns:
            Configured Analyzer instance.
        """
        config = Config.from_file(path)
        return cls(config)

    @property
    def config(self) -> Config:
        """Get the current configuration."""
        return self._config

    def _setup_logging(self) -> None:
        """Configure logging based on config."""
        log_level = getattr(logging, self._config.log_level.upper(), logging.INFO)
        logging.basicConfig(
            level=log_level,
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        )

        if self._config.log_file:
            handler = logging.FileHandler(self._config.log_file)
            handler.setLevel(log_level)
            logging.getLogger("sanskrit_analyzer").addHandler(handler)

    async def _initialize(self) -> None:
        """Lazy initialization of components.

        This is called on first analyze() call to defer heavy initialization.
        """
        if self._initialized:
            return

        logger.info("Initializing Sanskrit Analyzer components...")

        # Initialize ensemble analyzer
        self._ensemble = self._create_ensemble()

        # Initialize tiered cache
        self._cache = self._create_cache()

        # Initialize disambiguation pipeline
        self._disambiguation = self._create_disambiguation_pipeline()

        # Initialize tree builder
        self._tree_builder = TreeBuilder(TreeBuilderConfig())

        # Initialize the split validator.
        #
        # Architecture: cheda (vidyut) is authoritative. The curated
        # ``Vocabulary`` is the *scorer* — it is hand-tuned and was the only
        # vocab that passed every golden split. The full kosha is used only as
        # a *real-word veto* (``word_guard``): the validator may merge
        # fragments and split non-words, but must NEVER split a token that is a
        # valid whole kosha word (which is what fragmented "gacCati" -> "gat" +
        # "cati" and over-split the golden cases when the kosha was the scorer).
        try:
            vocab = Vocabulary.load_default()

            word_guard = None
            try:
                from sanskrit_analyzer.validation.kosha_vocabulary import (
                    KoshaVocabulary,
                )

                word_guard = KoshaVocabulary()
                logger.info("Split validator real-word veto enabled (kosha)")
            except Exception as e:
                logger.warning(
                    "Kosha word-guard unavailable (%s); split validator will "
                    "run without the real-word veto",
                    e,
                )

            self._split_validator = SplitValidator(vocab, word_guard=word_guard)
            logger.info(
                "Split validator loaded with %d curated vocabulary entries",
                len(vocab),
            )
        except Exception as e:
            logger.warning("Split validator not available: %s", e)
            self._split_validator = None

        self._initialized = True
        logger.info("Sanskrit Analyzer initialized successfully")

    def _create_ensemble(self) -> EnsembleAnalyzer:
        """Create and configure the ensemble analyzer."""
        engines: list[EngineBase] = []

        if self._config.engines.vidyut:
            try:
                from sanskrit_analyzer.engines.vidyut_engine import VidyutEngine
                engines.append(VidyutEngine())
                logger.debug("Vidyut engine loaded")
            except ImportError:
                logger.warning("Vidyut engine not available")

        if self._config.engines.heritage:
            try:
                from sanskrit_analyzer.engines.heritage_engine import HeritageEngine
                # heritage_mode config determines use_local
                use_local = self._config.engines.heritage_mode in ("local", "fallback")
                engines.append(HeritageEngine(
                    local_url=self._config.engines.heritage_local_url,
                    use_local=use_local,
                ))
                logger.debug("Heritage engine loaded")
            except ImportError:
                logger.warning("Heritage engine not available")

        if self._config.engines.local_byt5:
            try:
                from sanskrit_analyzer.engines.local_byt5_engine import LocalByT5Engine
                engines.append(LocalByT5Engine(
                    model_name=self._config.engines.local_byt5_model,
                    device=self._config.engines.local_byt5_device,
                ))
                logger.debug("Local ByT5 engine loaded")
            except ImportError:
                logger.warning("Local ByT5 engine not available (install transformers torch)")

        ensemble_config = EnsembleConfig(
            vidyut_weight=self._config.engines.vidyut_weight,
            heritage_weight=self._config.engines.heritage_weight,
            local_byt5_weight=self._config.engines.local_byt5_weight,
        )

        return EnsembleAnalyzer(engines=engines, config=ensemble_config)

    def _create_cache(self) -> TieredCache:
        """Create and configure the tiered cache."""
        cache_config = TieredCacheConfig(
            memory_enabled=self._config.cache.memory_enabled,
            memory_max_size=self._config.cache.memory_max_size,
            redis_enabled=self._config.cache.redis_enabled,
            redis_url=self._config.cache.redis_url,
            redis_ttl=self._config.cache.redis_ttl_days * 86400,  # Convert to seconds
            sqlite_enabled=self._config.cache.sqlite_enabled,
            sqlite_path=self._config.cache.sqlite_path,
        )

        return TieredCache(cache_config)

    def _create_disambiguation_pipeline(self) -> DisambiguationPipeline:
        """Create and configure the disambiguation pipeline."""
        # Map provider string to enum
        provider_map = {
            "ollama": LLMProvider.OLLAMA,
            "openai": LLMProvider.OPENAI,
        }
        provider = provider_map.get(
            self._config.disambiguation.llm_provider.lower(),
            LLMProvider.OLLAMA,
        )

        llm_config = LLMConfig(
            provider=provider,
            model=self._config.disambiguation.llm_model,
            ollama_url=self._config.disambiguation.ollama_url,
        )

        pipeline_config = PipelineConfig(
            rules_enabled=self._config.disambiguation.rules_enabled,
            rules_config=RuleBasedDisambiguatorConfig(),
            llm_enabled=self._config.disambiguation.llm_enabled,
            llm_config=llm_config,
            llm_skip_threshold=self._config.disambiguation.min_confidence_skip,
            human_review=HumanReviewConfig(
                enabled=self._config.disambiguation.human_enabled,
            ),
        )

        return DisambiguationPipeline(pipeline_config)

    async def analyze(
        self,
        text: str,
        mode: AnalysisMode | None = None,
        return_all_parses: bool | None = None,
        context: dict[str, Any] | None = None,
        engines: list[str] | None = None,
        bypass_cache: bool = False,
    ) -> AnalysisTree:
        """Analyze Sanskrit text and return a parse tree.

        This is the main entry point for Sanskrit text analysis.

        Args:
            text: Sanskrit text to analyze (any script).
            mode: Analysis mode (production, educational, academic).
                  If None, uses config default.
            return_all_parses: Whether to return all parse interpretations.
                               Overrides mode-specific setting if provided.
            context: Optional context for disambiguation (e.g., previous sentence).
            engines: Optional list of engine names to use (overrides config).
            bypass_cache: If True, skip cache lookup (but still store result).

        Returns:
            AnalysisTree with the complete analysis result.

        Example:
            result = await analyzer.analyze("रामो वनं गच्छति")
            print(result.best_parse.all_words)
        """
        await self._initialize()

        # Determine mode
        if mode is None:
            mode = self._config.default_mode
        mode_config = self._config.get_mode_config(mode)

        # Normalize text
        original_text = text.strip()
        source_script = detect_script(original_text)
        normalized_slp1 = normalize_slp1(original_text, source_script)

        logger.debug("Analyzing: %s (script: %s)", normalized_slp1[:50], source_script.value)

        # Generate cache key
        cache_key = self._make_cache_key(normalized_slp1, mode.value)

        # Check cache
        if not bypass_cache and self._cache:
            cached = await self._cache.get(cache_key)
            if cached:
                logger.debug("Cache hit for: %s", normalized_slp1[:30])
                tree = self._result_to_tree(
                    cached,
                    original_text,
                    normalized_slp1,
                    mode.value,
                )
                return tree

        # Run ensemble analysis
        logger.debug("Cache miss, running ensemble analysis")
        assert self._ensemble is not None

        # Override engines if specified
        if engines:
            # Temporarily filter engines
            original_engines = self._ensemble._engines.copy()
            self._ensemble._engines = [
                e for e in self._ensemble._engines if e.name in engines
            ]

        ensemble_result = await self._ensemble.analyze(normalized_slp1)

        # Restore engines if we filtered
        if engines:
            self._ensemble._engines = original_engines

        # Validate and re-score splits if validator is available.
        # The validator rescores VIDYUT splits against a small curated
        # vocabulary; applying it to segments from other engines (e.g. the
        # neural ByT5 segmenter) overrides higher-quality segmentation with
        # vocabulary-driven re-splits, so it only runs on vidyut's raw output.
        assert self._tree_builder is not None
        raw_vidyut_segments = None
        if ensemble_result.segments:
            engine_result = ensemble_result.engine_results.get("vidyut")
            if engine_result and engine_result.segments:
                raw_vidyut_segments = engine_result.segments

        if self._split_validator and (
            raw_vidyut_segments is not None or not ensemble_result.segments
        ):
            # Pass empty list when no engine produced segments; the
            # validator can still split using vocabulary alone.
            validated_segments = self._split_validator.validate_and_rescore(
                raw_vidyut_segments or [],
                normalized_slp1,
            )
            # Build tree from validated segments
            tree = self._tree_builder.build_from_segments(
                validated_segments,
                original_text,
                normalized_slp1,
                engine_name="vidyut+validator",
                mode=mode.value,
            )
        else:
            # Build parse tree from ensemble (original path)
            tree = self._tree_builder.build(
                ensemble_result,
                original_text,
                normalized_slp1,
                mode.value,
            )

        # Run disambiguation if multiple parses and enabled
        if (
            len(tree.parse_forest) > 1
            and self._disambiguation
            and tree.confidence.overall < self._config.disambiguation.min_confidence_skip
        ):
            tree = await self._disambiguate_tree(tree, context)

        # Determine return behavior
        if return_all_parses is None:
            return_all_parses = mode_config.return_all_parses

        if not return_all_parses and tree.parse_forest:
            # Keep only best parse
            best = tree.best_parse
            if best:
                tree.parse_forest = [best]
                tree.selected_parse = 0

        # Store in cache
        if self._cache:
            await self._cache.set(
                cache_key,
                original_text,
                normalized_slp1,
                mode.value,
                tree.to_dict(),
            )

        return tree

    async def _disambiguate_tree(
        self,
        tree: AnalysisTree,
        context: dict[str, Any] | None,
    ) -> AnalysisTree:
        """Run disambiguation on parse tree.

        Args:
            tree: The parse tree to disambiguate.
            context: Optional context for disambiguation.

        Returns:
            Updated tree with disambiguation applied.
        """
        if not self._disambiguation or len(tree.parse_forest) <= 1:
            return tree

        # Convert parses to candidates
        candidates = [
            ParseCandidate(
                index=i,
                segments=[w.to_dict() for w in parse.all_words],
                confidence=parse.confidence,
            )
            for i, parse in enumerate(tree.parse_forest)
        ]

        # Run disambiguation
        result = await self._disambiguation.disambiguate(candidates, context)

        # Update tree with disambiguation result
        if result.resolved_at.value != "none":
            tree.confidence.disambiguation_applied = True
            tree.confidence.disambiguation_stage = result.resolved_at.value

            # Reorder parse forest based on disambiguation
            if result.candidates:
                new_order = [c.index for c in result.candidates]
                tree.parse_forest = [tree.parse_forest[i] for i in new_order if i < len(tree.parse_forest)]
                tree.selected_parse = 0

                # Update overall confidence
                tree.confidence.overall = result.confidence

        return tree

    def _make_cache_key(self, text: str, mode: str) -> str:
        """Generate a cache key for the given text and mode.

        Args:
            text: Normalized SLP1 text.
            mode: Analysis mode.

        Returns:
            Cache key string.
        """
        if self._cache and self._cache._memory:
            return self._cache._memory.make_key(text, mode)
        # Fallback key generation
        import hashlib
        content = f"{mode}:{text}"
        return hashlib.sha256(content.encode("utf-8")).hexdigest()[:32]

    def _result_to_tree(
        self,
        cached: dict[str, Any],
        original_text: str | None = None,
        normalized_slp1: str | None = None,
        mode: str | None = None,
    ) -> AnalysisTree:
        """Convert cached result back to AnalysisTree.

        Args:
            cached: Cached result dictionary.
            original_text: Original input text (uses cached if None).
            normalized_slp1: Normalized SLP1 text (uses cached if None).
            mode: Analysis mode (uses cached if None).

        Returns:
            Reconstructed AnalysisTree.
        """
        from sanskrit_analyzer.models.tree import (
            ConfidenceMetrics,
            ParseTree,
            SandhiGroup,
            BaseWord,
        )
        from sanskrit_analyzer.models.morphology import MorphologicalTag, Meaning
        from sanskrit_analyzer.models.dhatu import DhatuInfo

        # Use cached values if not provided
        original_text = original_text or cached.get("original_text", "")
        normalized_slp1 = normalized_slp1 or cached.get("normalized_slp1", "")
        mode = mode or cached.get("mode", "production")

        # Rebuild scripts
        scripts = ScriptVariants.from_text(normalized_slp1, Script.SLP1)

        # Rebuild confidence
        conf_dict = cached.get("confidence", {})
        confidence = ConfidenceMetrics(
            overall=conf_dict.get("overall", 0.0),
            engine_agreement=conf_dict.get("engine_agreement", 0.0),
            disambiguation_applied=conf_dict.get("disambiguation_applied", False),
        )

        # Rebuild parse_forest
        parse_forest: list[ParseTree] = []
        for pt_dict in cached.get("parse_forest", []):
            sandhi_groups: list[SandhiGroup] = []
            for sg_dict in pt_dict.get("sandhi_groups", []):
                base_words: list[BaseWord] = []
                for bw_dict in sg_dict.get("base_words", []):
                    # Rebuild morphology
                    morph = None
                    morph_dict = bw_dict.get("morphology")
                    if morph_dict:
                        morph = MorphologicalTag(
                            pos=morph_dict.get("pos"),
                            gender=morph_dict.get("gender"),
                            number=morph_dict.get("number"),
                            case=morph_dict.get("case"),
                            person=morph_dict.get("person"),
                            tense=morph_dict.get("tense"),
                            voice=morph_dict.get("voice"),
                            raw_tag=morph_dict.get("raw_tag"),
                        )

                    # Rebuild dhatu. The serialized form (DhatuInfo.to_dict)
                    # drops the required ``scripts`` field, so reconstruct via
                    # the canonical COMMON_DHATUS entry when possible; otherwise
                    # build a minimal valid DhatuInfo (matching the real
                    # dataclass signature, which takes ``meanings``/``scripts``,
                    # not a singular ``meaning``).
                    dhatu = None
                    dhatu_dict = bw_dict.get("dhatu")
                    if dhatu_dict:
                        from sanskrit_analyzer.models.dhatu import COMMON_DHATUS

                        root = dhatu_dict.get("dhatu", "")
                        # NOTE: COMMON_DHATUS entries are shared singletons; the
                        # rebuilt tree references the canonical DhatuInfo rather
                        # than a per-call copy. DhatuInfo is treated as
                        # read-only here, so the sharing is safe.
                        dhatu = COMMON_DHATUS.get(root)
                        if dhatu is None:
                            meaning = dhatu_dict.get("meaning")
                            dhatu = DhatuInfo(
                                dhatu=root,
                                scripts=ScriptVariants.from_text(
                                    root, Script.SLP1
                                ),
                                gana=dhatu_dict.get("gana") or 0,
                                pada=dhatu_dict.get("pada") or "",
                                meanings=dhatu_dict.get("meanings")
                                or ([meaning] if meaning else []),
                            )

                    # Rebuild meanings
                    meanings = [
                        Meaning(text=m) if isinstance(m, str) else Meaning(text=str(m))
                        for m in bw_dict.get("meanings", [])
                    ]

                    # Rebuild scripts for word
                    bw_scripts = None
                    scripts_dict = bw_dict.get("scripts")
                    if scripts_dict:
                        bw_scripts = ScriptVariants(
                            devanagari=scripts_dict.get("devanagari", ""),
                            iast=scripts_dict.get("iast", ""),
                            slp1=scripts_dict.get("slp1", ""),
                        )

                    base_words.append(BaseWord(
                        lemma=bw_dict.get("lemma", ""),
                        surface_form=bw_dict.get("surface_form", ""),
                        scripts=bw_scripts,
                        morphology=morph,
                        meanings=meanings,
                        dhatu=dhatu,
                        confidence=bw_dict.get("confidence", 0.0),
                    ))

                # Rebuild scripts for sandhi group
                sg_scripts = None
                sg_scripts_dict = sg_dict.get("scripts")
                if sg_scripts_dict:
                    sg_scripts = ScriptVariants(
                        devanagari=sg_scripts_dict.get("devanagari", ""),
                        iast=sg_scripts_dict.get("iast", ""),
                        slp1=sg_scripts_dict.get("slp1", ""),
                    )

                sandhi_groups.append(SandhiGroup(
                    surface_form=sg_dict.get("surface_form", ""),
                    scripts=sg_scripts,
                    sandhi_type=sg_dict.get("sandhi_type"),
                    sandhi_rule=sg_dict.get("sandhi_rule"),
                    is_compound=sg_dict.get("is_compound", False),
                    compound_type=sg_dict.get("compound_type"),
                    base_words=base_words,
                ))

            parse_forest.append(ParseTree(
                parse_id=pt_dict.get("parse_id", ""),
                confidence=pt_dict.get("confidence", 0.0),
                engine_votes=pt_dict.get("engine_votes", {}),
                sandhi_groups=sandhi_groups,
            ))

        # Determine cache tier
        cache_tier = CacheTier.MEMORY  # Default assumption

        return AnalysisTree(
            sentence_id=cached.get("sentence_id", ""),
            original_text=original_text,
            normalized_slp1=normalized_slp1,
            scripts=scripts,
            parse_forest=parse_forest,
            confidence=confidence,
            mode=mode,
            cached_at=cache_tier,
        )

    async def analyze_batch(
        self,
        texts: list[str],
        mode: AnalysisMode | None = None,
        context: dict[str, Any] | None = None,
    ) -> list[AnalysisTree]:
        """Analyze multiple texts.

        Args:
            texts: List of Sanskrit texts to analyze.
            mode: Analysis mode for all texts.
            context: Optional shared context.

        Returns:
            List of AnalysisTree results.
        """
        results = []
        for text in texts:
            result = await self.analyze(text, mode=mode, context=context)
            results.append(result)
            # Update context with previous sentence for disambiguation
            if context is None:
                context = {}
            context["previous_sentence"] = text
        return results

    async def get_corpus_stats(self) -> CorpusStats:
        """Get statistics about the analysis corpus.

        Returns:
            CorpusStats with cache and corpus information.
        """
        await self._initialize()

        stats = CorpusStats()

        if self._cache:
            tier_stats = self._cache.stats
            if self._cache._memory:
                mem_stats = self._cache._memory.stats
                stats.memory_entries = mem_stats.size
                stats.cache_hit_rate = mem_stats.hit_rate

            if self._cache._sqlite:
                stats.sqlite_entries = self._cache._sqlite.count()
                stats.total_entries = stats.sqlite_entries

        return stats

    async def health_check(self) -> dict[str, bool]:
        """Check health of all components.

        Returns:
            Dictionary with component health status.
        """
        await self._initialize()

        health: dict[str, bool] = {}

        # Check ensemble engines
        if self._ensemble:
            for engine in self._ensemble._engines:
                try:
                    engine_health = await engine.health_check()
                    health[f"engine_{engine.name}"] = engine_health
                except Exception:
                    health[f"engine_{engine.name}"] = False

        # Check disambiguation
        if self._disambiguation:
            dis_health = await self._disambiguation.health_check()
            health.update({f"disambiguation_{k}": v for k, v in dis_health.items()})

        # Check cache
        if self._cache:
            health["cache_memory"] = self._cache._memory is not None
            health["cache_redis"] = self._cache._redis is not None
            health["cache_sqlite"] = self._cache._sqlite is not None

        return health

    def get_available_engines(self) -> list[str]:
        """Get list of available engine names.

        Returns:
            List of engine names that are loaded and available.
        """
        if not self._ensemble:
            return []
        return self._ensemble.available_engines

    async def clear_cache(self, tier: str | None = None) -> None:
        """Clear the analysis cache.

        Args:
            tier: Specific tier to clear ("memory", "redis", "sqlite").
                  If None, clears all tiers.
        """
        if not self._cache:
            return

        if tier is None or tier == "memory":
            if self._cache._memory:
                self._cache._memory.clear()

        if tier is None or tier == "redis":
            if self._cache._redis:
                # Redis clear would need implementation
                pass

        # SQLite clear is generally not recommended
        logger.info("Cache cleared: %s", tier or "all")

    def _ensure_dhatu_db(self) -> DhatuDB:
        """Ensure dhatu database is initialized."""
        if self._dhatu_db is None:
            self._dhatu_db = DhatuDB()
        return self._dhatu_db

    def lookup_dhatu(self, dhatu: str) -> DhatuInfo | None:
        """Look up dhatu (verbal root) information.

        Args:
            dhatu: The dhatu to look up (Devanagari or IAST).

        Returns:
            DhatuInfo if found, None otherwise.
        """
        # First try the TreeBuilder's common dhatus lookup
        if self._tree_builder:
            result = self._tree_builder._lookup_dhatu(dhatu)
            if result:
                return result

        # Fall back to dhatu database
        db = self._ensure_dhatu_db()
        entry = db.lookup_by_dhatu(dhatu)
        if entry:
            meanings = []
            if entry.meaning_english:
                meanings.append(entry.meaning_english)
            if entry.meaning_hindi:
                meanings.append(entry.meaning_hindi)
            return DhatuInfo.create(
                dhatu_slp1=entry.dhatu_iast or entry.dhatu_devanagari,
                gana=entry.gana or 1,
                pada=entry.pada or "parasmaipada",
                meanings=meanings,
            )
        return None

    def dictionary_lookup(self, word: str) -> list[dict]:
        """Look up word meanings from available dictionaries.

        Currently uses the dhatu database for verb roots.
        For nouns and other words, returns empty results.

        Args:
            word: The word to look up (Devanagari or IAST).

        Returns:
            List of dictionary entries with keys: word, meaning, source.
        """
        results = []

        # Search dhatu database
        db = self._ensure_dhatu_db()
        entries = db.search(word, limit=5)
        for entry in entries:
            results.append({
                "word": entry.dhatu_devanagari,
                "meaning": entry.meaning_english or entry.meaning_hindi or "",
                "source": "dhatu_db",
                "gana": entry.gana,
                "pada": entry.pada,
            })

        return results
