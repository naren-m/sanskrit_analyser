"""Parse tree builder for Sanskrit analysis.

This module converts engine results into the 4-level hierarchical
parse tree structure: AnalysisTree -> ParseTree -> SandhiGroup -> BaseWord.
"""

import hashlib
import logging
import uuid
from dataclasses import dataclass

from sanskrit_analyzer.engines.base import EngineResult, Segment
from sanskrit_analyzer.engines.runner import AnalyzedSegment, EngineRunResult
from sanskrit_analyzer.models.dhatu import COMMON_DHATUS, DhatuInfo
from sanskrit_analyzer.models.morphology import (
    Case,
    Gender,
    Meaning,
    MorphologicalTag,
    Number,
    PartOfSpeech,
    Person,
    Tense,
    Voice,
)
from sanskrit_analyzer.models.scripts import Script, ScriptVariants
from sanskrit_analyzer.models.tree import (
    AnalysisTree,
    BaseWord,
    CacheTier,
    CompoundType,
    ConfidenceMetrics,
    ParseTree,
    SandhiGroup,
)

logger = logging.getLogger(__name__)

_POS: dict[str, PartOfSpeech] = {p.value: p for p in PartOfSpeech} | {
    "adj": PartOfSpeech.ADJECTIVE,
    "adv": PartOfSpeech.ADVERB,
    "pron": PartOfSpeech.PRONOUN,
    "avyaya": PartOfSpeech.INDECLINABLE,
    "ind": PartOfSpeech.INDECLINABLE,
    "part": PartOfSpeech.PARTICIPLE,
    "inf": PartOfSpeech.INFINITIVE,
    "ger": PartOfSpeech.GERUND,
    "upasarga": PartOfSpeech.PREFIX,
    # Vidyut's own POS names.
    "subanta": PartOfSpeech.NOUN,
    "tinanta": PartOfSpeech.VERB,
}

# Morphology token -> enum member. Full enum values plus common abbreviations.
_MORPH_TOKENS: dict[str, Gender | Number | Case | Person | Tense | Voice] = {
    m.value: m for enum in (Gender, Number, Case, Person, Tense, Voice) for m in enum
} | {
    "m": Gender.MASCULINE, "mas": Gender.MASCULINE, "masc": Gender.MASCULINE,
    "f": Gender.FEMININE, "fem": Gender.FEMININE,
    "n": Gender.NEUTER, "neu": Gender.NEUTER, "neut": Gender.NEUTER,
    "sg": Number.SINGULAR, "sing": Number.SINGULAR,
    "du": Number.DUAL, "pl": Number.PLURAL,
    "nom": Case.NOMINATIVE, "acc": Case.ACCUSATIVE, "ins": Case.INSTRUMENTAL,
    "inst": Case.INSTRUMENTAL, "dat": Case.DATIVE, "abl": Case.ABLATIVE,
    "gen": Case.GENITIVE, "loc": Case.LOCATIVE, "voc": Case.VOCATIVE,
    "1": Person.FIRST, "2": Person.SECOND, "3": Person.THIRD,
    "pres": Tense.PRESENT, "impf": Tense.IMPERFECT, "imperf": Tense.IMPERFECT,
    "impv": Tense.IMPERATIVE, "imper": Tense.IMPERATIVE,
    "pot": Tense.POTENTIAL, "opt": Tense.POTENTIAL, "optative": Tense.POTENTIAL,
    "perf": Tense.PERFECT, "aor": Tense.AORIST, "fut": Tense.FUTURE,
    "laṭ": Tense.PRESENT, "laṅ": Tense.IMPERFECT, "loṭ": Tense.IMPERATIVE,
    "liṅ": Tense.POTENTIAL, "liṭ": Tense.PERFECT, "luṅ": Tense.AORIST,
    "lṛṭ": Tense.FUTURE, "luṭ": Tense.PERIPHRASTIC_FUTURE, "lṛṅ": Tense.CONDITIONAL,
    "act": Voice.ACTIVE, "parasmaipada": Voice.ACTIVE,
    "mid": Voice.MIDDLE, "ātmanepada": Voice.MIDDLE, "pass": Voice.PASSIVE,
}


@dataclass
class TreeBuilderConfig:
    """Configuration for the tree builder."""

    lookup_dhatus: bool = True  # Whether to look up dhatu info for verbs
    generate_meanings: bool = True  # Whether to include meanings
    infer_compounds: bool = True  # Whether to infer compound types


class TreeBuilder:
    """Builds 4-level parse trees from engine results.

    Converts the flat segment lists from engines into a hierarchical
    structure suitable for display and further analysis.

    Example:
        builder = TreeBuilder()
        result = await runner.analyze("rāmo vanam gacchati")
        tree = builder.build(result, "rāmo vanam gacchati", "rAmo vanam gacCati")
    """

    def __init__(self, config: TreeBuilderConfig | None = None) -> None:
        """Initialize the tree builder.

        Args:
            config: Builder configuration.
        """
        self._config = config or TreeBuilderConfig()

    def build(
        self,
        run_result: EngineRunResult,
        original_text: str,
        normalized_slp1: str,
        mode: str = "production",
    ) -> AnalysisTree:
        """Build an AnalysisTree from an engine run.

        Args:
            run_result: Result from EngineRunner.
            original_text: The original input text (any script).
            normalized_slp1: Text normalized to SLP1.
            mode: Analysis mode (production, educational, academic).

        Returns:
            Complete AnalysisTree with parse forest.
        """
        sentence_id = self._generate_sentence_id(normalized_slp1)
        scripts = ScriptVariants.from_text(normalized_slp1, Script.SLP1)

        # Build parse tree from the primary engine's segments
        parse_tree = self._build_parse_tree(
            run_result.segments,
            run_result.engine_results,
            run_result.overall_confidence,
        )

        # Calculate confidence metrics
        confidence = ConfidenceMetrics(
            overall=run_result.overall_confidence,
            engine_agreement=self._calculate_engine_agreement(run_result),
            disambiguation_applied=False,
        )

        return AnalysisTree(
            sentence_id=sentence_id,
            original_text=original_text,
            normalized_slp1=normalized_slp1,
            scripts=scripts,
            parse_forest=[parse_tree] if parse_tree.sandhi_groups else [],
            confidence=confidence,
            mode=mode,
            cached_at=CacheTier.NONE,
        )

    def build_from_segments(
        self,
        segments: list[Segment],
        original_text: str,
        normalized_slp1: str,
        engine_name: str = "unknown",
        mode: str = "production",
    ) -> AnalysisTree:
        """Build an AnalysisTree from raw segments (single engine).

        Args:
            segments: List of Segment objects from an engine.
            original_text: The original input text.
            normalized_slp1: Text normalized to SLP1.
            engine_name: Name of the source engine.
            mode: Analysis mode.

        Returns:
            Complete AnalysisTree.
        """
        sentence_id = self._generate_sentence_id(normalized_slp1)
        scripts = ScriptVariants.from_text(normalized_slp1, Script.SLP1)

        analyzed = [AnalyzedSegment.from_segment(seg, engine_name) for seg in segments]
        parse_tree = self._build_parse_tree_from_segments(analyzed, {engine_name: 1.0})

        # Average confidence
        avg_confidence = (
            sum(s.confidence for s in segments) / len(segments)
            if segments
            else 0.0
        )

        confidence = ConfidenceMetrics(
            overall=avg_confidence,
            engine_agreement=1.0,  # Single engine, perfect agreement
            disambiguation_applied=False,
        )

        return AnalysisTree(
            sentence_id=sentence_id,
            original_text=original_text,
            normalized_slp1=normalized_slp1,
            scripts=scripts,
            parse_forest=[parse_tree] if parse_tree.sandhi_groups else [],
            confidence=confidence,
            mode=mode,
            cached_at=CacheTier.NONE,
        )

    def _build_parse_tree(
        self,
        segments: list[AnalyzedSegment],
        engine_results: dict[str, EngineResult],
        overall_confidence: float,
    ) -> ParseTree:
        """Build a ParseTree from analyzed segments.

        Args:
            segments: Segments from the primary engine.
            engine_results: Per-engine results.
            overall_confidence: Overall confidence score.

        Returns:
            ParseTree with SandhiGroups.
        """
        engine_votes = {
            name: result.confidence
            for name, result in engine_results.items()
            if result.success
        }

        return self._build_parse_tree_from_segments(
            segments, engine_votes, overall_confidence
        )

    def _build_parse_tree_from_segments(
        self,
        segments: list[AnalyzedSegment],
        engine_votes: dict[str, float],
        confidence: float = 0.0,
    ) -> ParseTree:
        """Build ParseTree from analyzed segments.

        Args:
            segments: Analyzed segment list.
            engine_votes: Per-engine confidence scores.
            confidence: Overall confidence.

        Returns:
            ParseTree with SandhiGroups and BaseWords.
        """
        parse_id = self._generate_parse_id()

        # Group segments into SandhiGroups
        # For now, each segment becomes its own SandhiGroup
        # In the future, we could detect sandhi boundaries
        sandhi_groups = []

        for seg in segments:
            base_word = self._build_base_word(seg)
            sandhi_group = self._build_sandhi_group(seg, [base_word])
            sandhi_groups.append(sandhi_group)

        if not confidence and segments:
            confidence = sum(s.confidence for s in segments) / len(segments)

        return ParseTree(
            parse_id=parse_id,
            confidence=confidence,
            engine_votes=engine_votes,
            sandhi_groups=sandhi_groups,
        )

    def _build_sandhi_group(
        self,
        segment: AnalyzedSegment,
        base_words: list[BaseWord],
    ) -> SandhiGroup:
        """Build a SandhiGroup from a segment.

        Args:
            segment: The analyzed segment.
            base_words: Component words in this group.

        Returns:
            SandhiGroup containing the base words.
        """
        scripts = ScriptVariants.from_text(segment.surface, Script.SLP1)

        # Try to determine compound type if applicable
        is_compound = len(base_words) > 1
        compound_type = None
        if is_compound and self._config.infer_compounds:
            compound_type = self._infer_compound_type(base_words)

        return SandhiGroup(
            surface_form=segment.surface,
            scripts=scripts,
            sandhi_type=None,  # Could be inferred from segment info
            sandhi_rule=None,
            is_compound=is_compound,
            compound_type=compound_type,
            base_words=base_words,
        )

    def _build_base_word(self, segment: AnalyzedSegment) -> BaseWord:
        """Build a BaseWord from an analyzed segment.

        Args:
            segment: The analyzed segment.

        Returns:
            BaseWord with full analysis.
        """
        # Use lemma if available, otherwise fall back to surface form
        lemma = segment.lemma or segment.surface
        scripts = ScriptVariants.from_text(lemma, Script.SLP1)

        # Parse morphology if available
        morphology = self._parse_morphology(segment.morphology, segment.pos)

        # Look up dhatu if this is a verb
        dhatu = None
        if self._config.lookup_dhatus and self._is_verb(segment.pos, morphology):
            dhatu = self._lookup_dhatu(lemma)

        # Build meanings
        meanings: list[Meaning] = []
        if self._config.generate_meanings and segment.meanings:
            meanings = [Meaning(text=m) for m in segment.meanings]

        return BaseWord(
            lemma=lemma,
            surface_form=segment.surface,
            scripts=scripts,
            morphology=morphology,
            meanings=meanings,
            dhatu=dhatu,
            confidence=segment.confidence,
        )

    def _parse_morphology(
        self,
        morphology_str: str | None,
        pos: str | None,
    ) -> MorphologicalTag | None:
        """Parse a dotted morphology string (e.g. ``noun.masculine.nominative.singular``).

        Tokens are matched whole against enum values and a few abbreviations.
        Substring matching was tried before and misfired: "m." hit "nom.",
        "du" hit any token containing it.
        """
        pos_enum = _POS.get((pos or "").lower())
        if pos_enum is None:
            return None

        found: dict[type, object] = {}
        for token in (morphology_str or "").lower().split("."):
            value = _MORPH_TOKENS.get(token)
            if value is not None:
                found.setdefault(type(value), value)

        is_verb = pos_enum == PartOfSpeech.VERB
        return MorphologicalTag(
            pos=pos_enum,
            gender=found.get(Gender),  # type: ignore[arg-type]
            number=found.get(Number),  # type: ignore[arg-type]
            case=None if is_verb else found.get(Case),  # type: ignore[arg-type]
            person=found.get(Person) if is_verb else None,  # type: ignore[arg-type]
            tense=found.get(Tense) if is_verb else None,  # type: ignore[arg-type]
            voice=found.get(Voice) if is_verb else None,  # type: ignore[arg-type]
            raw_tag=morphology_str,
        )

    def _is_verb(
        self,
        pos: str | None,
        morphology: MorphologicalTag | None,
    ) -> bool:
        """Check if this segment represents a verb."""
        if morphology and morphology.pos == PartOfSpeech.VERB:
            return True
        # Vidyut emits the POS as "tinanta" (plain n); accept both that and
        # the diacritic spelling "tiṅanta".
        if pos and pos.lower() in ("verb", "v", "tinanta", "tiṅanta"):
            return True
        return False

    def _lookup_dhatu(self, lemma: str) -> DhatuInfo | None:
        """Look up dhatu information for a verb.

        Args:
            lemma: The lemma/root to look up.

        Returns:
            DhatuInfo if found, None otherwise.
        """
        # Check common dhatus first
        if lemma in COMMON_DHATUS:
            return COMMON_DHATUS[lemma]

        # In the future, this could query a dhatu database
        # For now, return None if not in common list
        return None

    def _infer_compound_type(self, base_words: list[BaseWord]) -> CompoundType | None:
        """Infer the compound type from component words.

        This is a simplified heuristic. Real compound analysis
        requires deeper grammatical understanding.

        Args:
            base_words: The component words.

        Returns:
            Inferred compound type or None.
        """
        if len(base_words) < 2:
            return None

        # Simple heuristics - could be much more sophisticated
        last_word = base_words[-1]
        if last_word.morphology:
            # If last word is adjective-like, might be bahuvrīhi
            if last_word.morphology.pos == PartOfSpeech.ADJECTIVE:
                return CompoundType.BAHUVRIHI

        # Default to tatpuruṣa (most common)
        return CompoundType.TATPURUSHA

    def _calculate_engine_agreement(self, result: EngineRunResult) -> float:
        """Calculate engine agreement score.

        Args:
            result: Engine run result.

        Returns:
            Agreement score (0.0 to 1.0).
        """
        if not result.segments:
            return 0.0

        return sum(s.agreement_score for s in result.segments) / len(result.segments)

    def _generate_sentence_id(self, text: str) -> str:
        """Generate a unique sentence ID.

        Args:
            text: The normalized text.

        Returns:
            Unique sentence identifier.
        """
        # Use hash of text + random UUID for uniqueness
        text_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()[:8]
        return f"sent_{text_hash}_{uuid.uuid4().hex[:8]}"

    def _generate_parse_id(self) -> str:
        """Generate a unique parse ID.

        Returns:
            Unique parse identifier.
        """
        return f"parse_{uuid.uuid4().hex[:12]}"
