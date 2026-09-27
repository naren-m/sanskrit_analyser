"""Main Analyzer class - the primary public interface for Sanskrit analysis.

This module provides the high-level Analyzer class that orchestrates the entire
analysis pipeline: normalization -> caching -> engine run -> tree building
-> disambiguation -> caching -> result return.
"""

import asyncio
import logging
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any

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
from sanskrit_analyzer.engines.base import EngineBase, Segment
from sanskrit_analyzer.engines.runner import EngineRunner
from sanskrit_analyzer.models.dhatu import DhatuInfo, Pada
from sanskrit_analyzer.models.scripts import Script, ScriptVariants
from sanskrit_analyzer.models.tree import AnalysisTree, BaseWord, CacheTier
from sanskrit_analyzer.tree_builder import TreeBuilder, TreeBuilderConfig
from sanskrit_analyzer.utils.normalize import detect_script, normalize_slp1
from sanskrit_analyzer.validation.split_validator import SplitValidator
from sanskrit_analyzer.validation.vocabulary import Vocabulary

logger = logging.getLogger(__name__)

# Confidence cap for splits made from the curated vocabulary alone, when no
# engine produced segments (e.g. the vidyut bundle is missing).
_VOCAB_ONLY_CONFIDENCE = 0.3

# How many of the split validator's ranked splits become parses when
# disambiguation is on. Matches the rules stage's max_candidates_to_keep.
_MAX_PARSES = 5


def _candidate_segment(word: BaseWord) -> dict[str, Any]:
    """A BaseWord as the disambiguation stages read it.

    The rules and the LLM prompt want top-level ``pos`` and ``surface`` and an
    IAST lemma (the frequency lists are IAST); ``BaseWord.to_dict`` nests pos
    under morphology, names the surface ``surface_form`` and keeps SLP1.
    """
    seg = word.to_dict()
    seg["surface"] = word.surface_form
    seg["pos"] = word.morphology.pos.value if word.morphology else None
    if word.scripts:
        seg["lemma"] = word.scripts.iast
    return seg


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
    3. If cache miss, run the configured engines (Vidyut by default)
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
            config: Analyzer configuration. If None, uses defaults with
                SANSKRIT_* env var overrides applied.
        """
        self._config = config or Config._apply_env_overrides(Config())
        self._setup_logging()

        # Initialize components (lazy)
        self._runner: EngineRunner | None = None
        self._cache: TieredCache | None = None
        self._disambiguation: DisambiguationPipeline | None = None
        self._tree_builder: TreeBuilder | None = None
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
        # Only the package logger: this is a library, and basicConfig would
        # install a root handler inside the host app (ramayanam, yoga_sutras).
        log_level = getattr(logging, self._config.log_level.upper(), logging.INFO)
        package_logger = logging.getLogger("sanskrit_analyzer")
        package_logger.setLevel(log_level)

        if self._config.log_file:
            handler = logging.FileHandler(self._config.log_file)
            handler.setLevel(log_level)
            package_logger.addHandler(handler)

    async def _initialize(self) -> None:
        """Lazy initialization of components.

        This is called on first analyze() call to defer heavy initialization.
        """
        if self._initialized:
            return

        logger.info("Initializing Sanskrit Analyzer components...")

        # Initialize the engine runner
        self._runner = self._create_engine_runner()

        # Initialize tiered cache. initialize() connects Redis; without it the
        # tier stayed unconnected and every get/set was a silent no-op.
        self._cache = self._create_cache()
        if self._cache:
            await self._cache.initialize()

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

    def _create_engine_runner(self) -> EngineRunner:
        """Create the engine runner, in priority order."""
        engines: list[EngineBase] = []

        if self._config.engines.vidyut:
            try:
                from sanskrit_analyzer.engines.vidyut_engine import VidyutEngine
                engines.append(VidyutEngine())
                logger.debug("Vidyut engine loaded")
            except ImportError:
                logger.warning("Vidyut engine not available")

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

        return EngineRunner(engines=engines)

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
            openai_api_key=self._config.disambiguation.openai_api_key,
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

        # Engine and context overrides change the result but are not part of
        # the key, so those requests neither read nor write the shared cache.
        cacheable = self._cache is not None and not engines and not context
        cache_key = self._cache.make_key(normalized_slp1, mode.value) if cacheable else ""

        tree = None
        if cacheable and not bypass_cache:
            cached = await self._cache.get(cache_key)
            if cached:
                logger.debug("Cache hit for: %s", normalized_slp1[:30])
                tree = self._result_to_tree(cached, original_text, normalized_slp1, mode.value)

        if tree is None:
            tree = await self._run_pipeline(original_text, normalized_slp1, mode, engines, context)
            # Cache the full forest; return_all_parses is applied per request below.
            if cacheable:
                await self._cache.set(
                    cache_key,
                    original_text,
                    normalized_slp1,
                    mode.value,
                    tree.to_dict(),
                )

        if return_all_parses is None:
            return_all_parses = mode_config.return_all_parses

        if not return_all_parses and tree.parse_forest:
            best = tree.best_parse
            if best:
                tree.parse_forest = [best]
                tree.selected_parse = 0

        return tree

    async def _run_pipeline(
        self,
        original_text: str,
        normalized_slp1: str,
        mode: AnalysisMode,
        engines: list[str] | None,
        context: dict[str, Any] | None,
    ) -> AnalysisTree:
        """Run engines, validation, tree building and disambiguation (cache miss path)."""
        logger.debug("Cache miss, running engine analysis")
        assert self._runner is not None

        run_result = await self._runner.analyze(normalized_slp1, engines=engines)

        # Validate and re-score splits if validator is available.
        # The validator rescores VIDYUT splits against a small curated
        # vocabulary; applying it to segments from other engines (e.g. the
        # neural ByT5 segmenter) overrides higher-quality segmentation with
        # vocabulary-driven re-splits, so it only runs on vidyut's raw output.
        assert self._tree_builder is not None
        raw_vidyut_segments = None
        if run_result.segments:
            engine_result = run_result.engine_results.get("vidyut")
            if engine_result and engine_result.segments:
                raw_vidyut_segments = engine_result.segments

        if not run_result.segments and run_result.errors:
            logger.warning("No engine produced segments: %s", "; ".join(run_result.errors))

        if self._split_validator and (
            raw_vidyut_segments is not None or not run_result.segments
        ):
            # Pass empty list when no engine produced segments; the
            # validator can still split using vocabulary alone. The validator
            # is CPU-bound Python (quadratic on long unspaced input), so it runs
            # off the event loop.
            ranked = await asyncio.to_thread(
                self._split_validator.rank_candidates,
                raw_vidyut_segments or [],
                normalized_slp1,
            )
            # Without disambiguation only the validator's pick is a parse;
            # with it, the runner-ups join the forest for the pipeline to rank.
            ranked = ranked[: _MAX_PARSES if self._config.disambiguation.enabled else 1]
            engine_name = "vidyut+validator"
            if raw_vidyut_segments is None:
                # A ~100-word vocabulary alone is a guess, not an analysis;
                # don't let it report the default confidence of 1.0.
                engine_name = "validator"
                for _, segs in ranked:
                    for seg in segs:
                        seg.confidence = min(seg.confidence, _VOCAB_ONLY_CONFIDENCE)
            tree = self._build_forest(
                ranked, original_text, normalized_slp1, engine_name, mode.value
            )
        else:
            # Build parse tree from the engine run (original path)
            tree = self._tree_builder.build(
                run_result,
                original_text,
                normalized_slp1,
                mode.value,
            )

        # The forest only holds alternatives when disambiguation is enabled.
        # No gate on tree.confidence.overall: that is the engine's constant
        # (0.9 vidyut, 1.0 vocabulary), not a measure of ambiguity, and it
        # skipped every validator-built tree. min_confidence_skip still gates
        # the LLM stage inside the pipeline.
        if len(tree.parse_forest) > 1:
            tree = await self._disambiguate_tree(tree, context)

        return tree

    def _build_forest(
        self,
        ranked: list[tuple[float, list[Segment]]],
        original_text: str,
        normalized_slp1: str,
        engine_name: str,
        mode: str,
    ) -> AnalysisTree:
        """Build a tree whose forest holds the validator's ranked splits, best first.

        An alternative's confidence is its segment confidence scaled by
        ``exp(score - best_score)``: a tie keeps the full value, and each point
        of validator score behind the best costs a factor of e. The rules stage
        then only moves near-ties, and its 0.3 floor prunes the long tail.
        """
        assert self._tree_builder is not None
        best_score, best_segments = ranked[0] if ranked else (0.0, [])
        tree = self._tree_builder.build_from_segments(
            best_segments, original_text, normalized_slp1, engine_name=engine_name, mode=mode
        )
        for score, segments in ranked[1:]:
            alt = self._tree_builder.build_from_segments(
                segments, original_text, normalized_slp1, engine_name=engine_name, mode=mode
            ).parse_forest
            if alt:
                alt[0].confidence *= math.exp(score - best_score)
                tree.parse_forest.extend(alt)
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

        candidates = [
            ParseCandidate(
                index=i,
                segments=[_candidate_segment(w) for w in parse.all_words],
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

            # Reorder (and prune) the forest to the pipeline's ranking. The
            # LLM stage reorders without touching confidence, so selected_parse
            # pins the pick rather than best_parse's max-confidence fallback.
            if result.candidates:
                forest = tree.parse_forest
                tree.parse_forest = [forest[c.index] for c in result.candidates]
                tree.selected_parse = 0

                # Update overall confidence
                tree.confidence.overall = result.confidence

        return tree

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
        from sanskrit_analyzer.models.morphology import Meaning, MorphologicalTag
        from sanskrit_analyzer.models.tree import (
            BaseWord,
            ConfidenceMetrics,
            ParseTree,
            SandhiGroup,
        )

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
                    morph_dict = bw_dict.get("morphology")
                    morph = MorphologicalTag.from_dict(morph_dict) if morph_dict else None

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
            selected_parse=cached.get("selected_parse"),
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
            # Update context with previous sentence for disambiguation; copy so
            # the caller's dict is not mutated.
            context = {**(context or {}), "previous_sentence": text}
        return results

    async def get_corpus_stats(self) -> CorpusStats:
        """Get statistics about the analysis corpus.

        Returns:
            CorpusStats with cache and corpus information.
        """
        await self._initialize()

        stats = CorpusStats()

        if self._cache:
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

        # Check engines
        if self._runner:
            for engine in self._runner._engines:
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
        if not self._runner:
            return []
        return self._runner.available_engines

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

    def lookup_dhatu(self, dhatu: str) -> DhatuInfo | None:
        """Look up dhatu (verbal root) information in the Dhātupāṭha.

        Args:
            dhatu: The dhatu to look up (Devanagari, IAST or SLP1).

        Returns:
            DhatuInfo if found, None otherwise.
        """
        # Imported here, not at module scope: sanskrit_analyzer.dhatu pulls in
        # deep_read, which imports back into dhatu.identifier. See
        # tests/test_import_boundaries.py for the boundaries that do hold.
        from sanskrit_analyzer.dhatu import conjugation
        from sanskrit_analyzer.dhatu.dhatupatha import get_dhatu_kosha

        # First try the TreeBuilder's common dhatus lookup
        if self._tree_builder:
            result = self._tree_builder._lookup_dhatu(dhatu)
            if result:
                return result

        entries = get_dhatu_kosha().find(dhatu)
        if not entries:
            return None

        # A root can hold several Dhātupāṭha entries (√kṛ is in gaṇa 5 and 8);
        # prefer the hand-curated reading.
        entry = next((e for e in entries if e["curated"]), entries[0])
        padas = conjugation.padas_for(entry["code"])
        if len(padas) > 1:
            pada = Pada.UBHAYAPADA
        elif padas:
            pada = padas[0]
        else:
            # Derivation needs the vidyut bundle; say so rather than guessing.
            pada = "unknown"
        return DhatuInfo.create(
            dhatu_slp1=entry["core_root"],
            gana=int(entry["gana"]),
            pada=pada,
            meanings=[m for m in (entry["artha_iast"], entry["artha_deva"]) if m],
        )

    def dictionary_lookup(self, word: str) -> list[dict]:
        """Look up word meanings in the Dhātupāṭha.

        Only verbal roots are covered; the artha returned is the Dhātupāṭha's
        own Sanskrit gloss, not an English translation. Nouns and other words
        return an empty list.

        Args:
            word: The word to look up (Devanagari, IAST or SLP1).

        Returns:
            List of dictionary entries with keys: word, meaning, source.
        """
        from sanskrit_analyzer.dhatu.dhatupatha import get_dhatu_kosha

        return [
            {
                "word": entry["dhatu_deva"],
                "meaning": entry["artha_iast"],
                "source": "dhatupatha",
                "gana": int(entry["gana"]),
                "code": entry["code"],
            }
            for entry in get_dhatu_kosha().search(word, limit=5)
        ]
