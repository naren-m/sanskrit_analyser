"""Parse tree builder for Sanskrit analysis.

This module converts ensemble engine results into the 4-level hierarchical
parse tree structure: AnalysisTree -> ParseTree -> SandhiGroup -> BaseWord.
"""

import hashlib
import logging
import uuid
from dataclasses import dataclass

from sanskrit_analyzer.engines.base import EngineResult, Segment
from sanskrit_analyzer.engines.ensemble import EnsembleResult, MergedSegment
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


@dataclass
class TreeBuilderConfig:
    """Configuration for the tree builder."""

    lookup_dhatus: bool = True  # Whether to look up dhatu info for verbs
    generate_meanings: bool = True  # Whether to include meanings
    infer_compounds: bool = True  # Whether to infer compound types


class TreeBuilder:
    """Builds 4-level parse trees from ensemble analysis results.

    Converts the flat segment lists from engines into a hierarchical
    structure suitable for display and further analysis.

    Example:
        builder = TreeBuilder()
        result = await ensemble.analyze("rāmo vanam gacchati")
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
        ensemble_result: EnsembleResult,
        original_text: str,
        normalized_slp1: str,
        mode: str = "production",
    ) -> AnalysisTree:
        """Build an AnalysisTree from ensemble results.

        Args:
            ensemble_result: Result from EnsembleAnalyzer.
            original_text: The original input text (any script).
            normalized_slp1: Text normalized to SLP1.
            mode: Analysis mode (production, educational, academic).

        Returns:
            Complete AnalysisTree with parse forest.
        """
        sentence_id = self._generate_sentence_id(normalized_slp1)
        scripts = ScriptVariants.from_text(normalized_slp1, Script.SLP1)

        # Build parse tree from ensemble segments
        parse_tree = self._build_parse_tree(
            ensemble_result.segments,
            ensemble_result.engine_results,
            ensemble_result.overall_confidence,
        )

        # Calculate confidence metrics
        confidence = ConfidenceMetrics(
            overall=ensemble_result.overall_confidence,
            engine_agreement=self._calculate_engine_agreement(ensemble_result),
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

        # Convert segments to merged format
        merged = [self._segment_to_merged(seg, engine_name) for seg in segments]

        # Build parse tree
        parse_tree = self._build_parse_tree_from_merged(merged, {engine_name: 1.0})

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
        segments: list[MergedSegment],
        engine_results: dict[str, EngineResult],
        overall_confidence: float,
    ) -> ParseTree:
        """Build a ParseTree from merged segments.

        Args:
            segments: Merged segments from ensemble.
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

        return self._build_parse_tree_from_merged(
            segments, engine_votes, overall_confidence
        )

    def _build_parse_tree_from_merged(
        self,
        segments: list[MergedSegment],
        engine_votes: dict[str, float],
        confidence: float = 0.0,
    ) -> ParseTree:
        """Build ParseTree from merged segments.

        Args:
            segments: Merged segment list.
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
        segment: MergedSegment,
        base_words: list[BaseWord],
    ) -> SandhiGroup:
        """Build a SandhiGroup from a segment.

        Args:
            segment: The merged segment.
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

    def _build_base_word(self, segment: MergedSegment) -> BaseWord:
        """Build a BaseWord from a merged segment.

        Args:
            segment: The merged segment.

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
        """Parse a morphology string into a MorphologicalTag.

        Args:
            morphology_str: Raw morphology string from engine.
            pos: Part of speech string.

        Returns:
            MorphologicalTag or None if unparseable.
        """
        if not pos:
            return None

        pos_lower = pos.lower()

        # Determine part of speech
        pos_enum = self._parse_pos(pos_lower)
        if pos_enum is None:
            return None

        # Parse additional morphological features based on POS
        gender = None
        number = None
        case = None
        person = None
        tense = None
        voice = None

        if morphology_str:
            morph_lower = morphology_str.lower()

            # Parse gender
            if "masculine" in morph_lower or "mas" in morph_lower or "m." in morph_lower:
                gender = Gender.MASCULINE
            elif "feminine" in morph_lower or "fem" in morph_lower or "f." in morph_lower:
                gender = Gender.FEMININE
            elif "neuter" in morph_lower or "neu" in morph_lower or "n." in morph_lower:
                gender = Gender.NEUTER

            # Parse number
            if "singular" in morph_lower or "sing" in morph_lower or "sg" in morph_lower:
                number = Number.SINGULAR
            elif "dual" in morph_lower or "du" in morph_lower:
                number = Number.DUAL
            elif "plural" in morph_lower or "pl" in morph_lower:
                number = Number.PLURAL

            # Parse case for nominals
            if pos_enum in (PartOfSpeech.NOUN, PartOfSpeech.ADJECTIVE, PartOfSpeech.PRONOUN):
                case = self._parse_case(morph_lower)

            # Parse verb features
            if pos_enum == PartOfSpeech.VERB:
                person = self._parse_person(morph_lower)
                tense = self._parse_tense(morph_lower)
                voice = self._parse_voice(morph_lower)

        return MorphologicalTag(
            pos=pos_enum,
            gender=gender,
            number=number,
            case=case,
            person=person,
            tense=tense,
            voice=voice,
            raw_tag=morphology_str,
        )

    def _parse_pos(self, pos_str: str) -> PartOfSpeech | None:
        """Parse part of speech from string."""
        pos_map = {
            "noun": PartOfSpeech.NOUN,
            "verb": PartOfSpeech.VERB,
            "adj": PartOfSpeech.ADJECTIVE,
            "adjective": PartOfSpeech.ADJECTIVE,
            "adverb": PartOfSpeech.ADVERB,
            "adv": PartOfSpeech.ADVERB,
            "pronoun": PartOfSpeech.PRONOUN,
            "pron": PartOfSpeech.PRONOUN,
            "indeclinable": PartOfSpeech.INDECLINABLE,
            "avyaya": PartOfSpeech.INDECLINABLE,
            "ind": PartOfSpeech.INDECLINABLE,
            "participle": PartOfSpeech.PARTICIPLE,
            "part": PartOfSpeech.PARTICIPLE,
            "infinitive": PartOfSpeech.INFINITIVE,
            "inf": PartOfSpeech.INFINITIVE,
            "gerund": PartOfSpeech.GERUND,
            "ger": PartOfSpeech.GERUND,
            "prefix": PartOfSpeech.PREFIX,
            "upasarga": PartOfSpeech.PREFIX,
            "particle": PartOfSpeech.PARTICLE,
        }
        return pos_map.get(pos_str)

    def _parse_case(self, morph_str: str) -> Case | None:
        """Parse case from morphology string."""
        case_map = {
            "nominative": Case.NOMINATIVE,
            "nom": Case.NOMINATIVE,
            "accusative": Case.ACCUSATIVE,
            "acc": Case.ACCUSATIVE,
            "instrumental": Case.INSTRUMENTAL,
            "ins": Case.INSTRUMENTAL,
            "dative": Case.DATIVE,
            "dat": Case.DATIVE,
            "ablative": Case.ABLATIVE,
            "abl": Case.ABLATIVE,
            "genitive": Case.GENITIVE,
            "gen": Case.GENITIVE,
            "locative": Case.LOCATIVE,
            "loc": Case.LOCATIVE,
            "vocative": Case.VOCATIVE,
            "voc": Case.VOCATIVE,
        }
        for key, value in case_map.items():
            if key in morph_str:
                return value
        return None

    def _parse_person(self, morph_str: str) -> Person | None:
        """Parse person from morphology string."""
        if "1" in morph_str or "first" in morph_str:
            return Person.FIRST
        if "2" in morph_str or "second" in morph_str:
            return Person.SECOND
        if "3" in morph_str or "third" in morph_str:
            return Person.THIRD
        return None

    def _parse_tense(self, morph_str: str) -> Tense | None:
        """Parse tense from morphology string."""
        tense_map = {
            "present": Tense.PRESENT,
            "pres": Tense.PRESENT,
            "laṭ": Tense.PRESENT,
            "imperfect": Tense.IMPERFECT,
            "imperf": Tense.IMPERFECT,
            "laṅ": Tense.IMPERFECT,
            "imperative": Tense.IMPERATIVE,
            "imper": Tense.IMPERATIVE,
            "loṭ": Tense.IMPERATIVE,
            "potential": Tense.POTENTIAL,
            "pot": Tense.POTENTIAL,
            "optative": Tense.POTENTIAL,
            "liṅ": Tense.POTENTIAL,
            "perfect": Tense.PERFECT,
            "perf": Tense.PERFECT,
            "liṭ": Tense.PERFECT,
            "aorist": Tense.AORIST,
            "aor": Tense.AORIST,
            "luṅ": Tense.AORIST,
            "future": Tense.FUTURE,
            "fut": Tense.FUTURE,
            "lṛṭ": Tense.FUTURE,
        }
        for key, value in tense_map.items():
            if key in morph_str:
                return value
        return None

    def _parse_voice(self, morph_str: str) -> Voice | None:
        """Parse voice from morphology string."""
        if "active" in morph_str or "parasmaipada" in morph_str or "para" in morph_str:
            return Voice.ACTIVE
        if "middle" in morph_str or "ātmanepada" in morph_str or "atma" in morph_str:
            return Voice.MIDDLE
        if "passive" in morph_str:
            return Voice.PASSIVE
        return None

    def _is_verb(
        self,
        pos: str | None,
        morphology: MorphologicalTag | None,
    ) -> bool:
        """Check if this segment represents a verb."""
        if morphology and morphology.pos == PartOfSpeech.VERB:
            return True
        if pos and pos.lower() in ("verb", "v", "tiṅanta"):
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

    def _segment_to_merged(
        self,
        segment: Segment,
        engine_name: str,
    ) -> MergedSegment:
        """Convert a Segment to MergedSegment.

        Args:
            segment: The segment to convert.
            engine_name: Name of the source engine.

        Returns:
            MergedSegment representation.
        """
        return MergedSegment(
            surface=segment.surface,
            lemma=segment.lemma,
            morphology=segment.morphology,
            confidence=segment.confidence,
            pos=segment.pos,
            meanings=segment.meanings or [],
            engine_votes={engine_name: segment.confidence},
            agreement_score=1.0,
        )

    def _calculate_engine_agreement(self, result: EnsembleResult) -> float:
        """Calculate engine agreement score.

        Args:
            result: Ensemble result.

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
