"""Tests for parse tree builder."""

import pytest

from sanskrit_analyzer.engines.base import EngineResult, Segment
from sanskrit_analyzer.engines.ensemble import EnsembleResult, MergedSegment
from sanskrit_analyzer.models.morphology import Case, Gender, Number, PartOfSpeech
from sanskrit_analyzer.models.tree import CacheTier
from sanskrit_analyzer.tree_builder import TreeBuilder, TreeBuilderConfig


class TestTreeBuilderConfig:
    """Tests for TreeBuilderConfig dataclass."""

    def test_defaults(self) -> None:
        """Test default configuration."""
        config = TreeBuilderConfig()
        assert config.lookup_dhatus is True
        assert config.generate_meanings is True
        assert config.infer_compounds is True

    def test_custom_config(self) -> None:
        """Test custom configuration."""
        config = TreeBuilderConfig(
            lookup_dhatus=False,
            generate_meanings=False,
        )
        assert config.lookup_dhatus is False
        assert config.generate_meanings is False


class TestTreeBuilder:
    """Tests for TreeBuilder class."""

    @pytest.fixture
    def builder(self) -> TreeBuilder:
        """Create a builder instance."""
        return TreeBuilder()

    @pytest.fixture
    def simple_segments(self) -> list[MergedSegment]:
        """Create simple test segments."""
        return [
            MergedSegment(
                surface="rAmaH",
                lemma="rAma",
                morphology="noun.masculine.singular.nominative",
                confidence=0.9,
                pos="noun",
                meanings=["Rama", "pleasing"],
                engine_votes={"vidyut": 0.9, "dharmamitra": 0.85},
                agreement_score=0.9,
            ),
            MergedSegment(
                surface="gacCati",
                lemma="gam",
                morphology="verb.third.singular.present.active",
                confidence=0.95,
                pos="verb",
                meanings=["goes", "walks"],
                engine_votes={"vidyut": 0.95, "dharmamitra": 0.92},
                agreement_score=0.95,
            ),
        ]

    @pytest.fixture
    def ensemble_result(self, simple_segments: list[MergedSegment]) -> EnsembleResult:
        """Create ensemble result for testing."""
        return EnsembleResult(
            segments=simple_segments,
            engine_results={
                "vidyut": EngineResult(
                    engine="vidyut",
                    segments=[
                        Segment(surface="rAmaH", lemma="rAma", confidence=0.9, pos="noun"),
                        Segment(surface="gacCati", lemma="gam", confidence=0.95, pos="verb"),
                    ],
                    confidence=0.92,
                ),
                "dharmamitra": EngineResult(
                    engine="dharmamitra",
                    segments=[
                        Segment(surface="rAmaH", lemma="rAma", confidence=0.85, pos="noun"),
                        Segment(surface="gacCati", lemma="gam", confidence=0.92, pos="verb"),
                    ],
                    confidence=0.88,
                ),
            },
            overall_confidence=0.9,
            agreement_level="high",
        )

    def test_init(self, builder: TreeBuilder) -> None:
        """Test initialization."""
        assert builder._config.lookup_dhatus is True

    def test_build_basic(
        self,
        builder: TreeBuilder,
        ensemble_result: EnsembleResult,
    ) -> None:
        """Test basic tree building."""
        tree = builder.build(
            ensemble_result,
            original_text="rāmaḥ gacchati",
            normalized_slp1="rAmaH gacCati",
        )

        assert tree.sentence_id.startswith("sent_")
        assert tree.original_text == "rāmaḥ gacchati"
        assert tree.normalized_slp1 == "rAmaH gacCati"
        assert len(tree.parse_forest) == 1
        assert tree.confidence.overall == 0.9

    def test_build_parse_tree_structure(
        self,
        builder: TreeBuilder,
        ensemble_result: EnsembleResult,
    ) -> None:
        """Test parse tree structure."""
        tree = builder.build(
            ensemble_result,
            original_text="rāmaḥ gacchati",
            normalized_slp1="rAmaH gacCati",
        )

        parse = tree.best_parse
        assert parse is not None
        assert parse.parse_id.startswith("parse_")
        assert len(parse.sandhi_groups) == 2
        assert parse.word_count == 2

    def test_build_sandhi_group(
        self,
        builder: TreeBuilder,
        ensemble_result: EnsembleResult,
    ) -> None:
        """Test sandhi group structure."""
        tree = builder.build(
            ensemble_result,
            original_text="rāmaḥ gacchati",
            normalized_slp1="rAmaH gacCati",
        )

        parse = tree.best_parse
        assert parse is not None

        group = parse.sandhi_groups[0]
        assert group.surface_form == "rAmaH"
        assert group.word_count == 1
        assert group.is_single_word is True

    def test_build_base_word(
        self,
        builder: TreeBuilder,
        ensemble_result: EnsembleResult,
    ) -> None:
        """Test base word structure."""
        tree = builder.build(
            ensemble_result,
            original_text="rāmaḥ gacchati",
            normalized_slp1="rAmaH gacCati",
        )

        parse = tree.best_parse
        assert parse is not None

        word = parse.sandhi_groups[0].base_words[0]
        assert word.lemma == "rAma"
        assert word.surface_form == "rAmaH"
        assert word.scripts.slp1 == "rAma"
        assert len(word.meanings) == 2

    def test_build_verb_with_dhatu(
        self,
        builder: TreeBuilder,
        ensemble_result: EnsembleResult,
    ) -> None:
        """Test verb with dhatu lookup."""
        tree = builder.build(
            ensemble_result,
            original_text="rāmaḥ gacchati",
            normalized_slp1="rAmaH gacCati",
        )

        parse = tree.best_parse
        assert parse is not None

        # Second word is verb
        verb_word = parse.sandhi_groups[1].base_words[0]
        assert verb_word.lemma == "gam"
        assert verb_word.is_verb_derived is True
        assert verb_word.dhatu is not None
        assert verb_word.dhatu.dhatu == "gam"

    def test_build_morphology_parsing(
        self,
        builder: TreeBuilder,
        ensemble_result: EnsembleResult,
    ) -> None:
        """Test morphology parsing."""
        tree = builder.build(
            ensemble_result,
            original_text="rāmaḥ gacchati",
            normalized_slp1="rAmaH gacCati",
        )

        parse = tree.best_parse
        assert parse is not None

        # First word is noun
        noun_word = parse.sandhi_groups[0].base_words[0]
        assert noun_word.morphology is not None
        assert noun_word.morphology.pos == PartOfSpeech.NOUN
        assert noun_word.morphology.gender == Gender.MASCULINE
        assert noun_word.morphology.number == Number.SINGULAR
        assert noun_word.morphology.case == Case.NOMINATIVE

    def test_build_from_segments(self, builder: TreeBuilder) -> None:
        """Test building from raw segments."""
        segments = [
            Segment(
                surface="vanam",
                lemma="vana",
                morphology="noun.neuter.singular.accusative",
                confidence=0.85,
                pos="noun",
                meanings=["forest"],
            ),
        ]

        tree = builder.build_from_segments(
            segments,
            original_text="vanam",
            normalized_slp1="vanam",
            engine_name="test_engine",
        )

        assert len(tree.parse_forest) == 1
        assert tree.confidence.engine_agreement == 1.0

        word = tree.all_words[0]
        assert word.lemma == "vana"

    def test_build_empty_segments(self, builder: TreeBuilder) -> None:
        """Test building with empty segments."""
        result = EnsembleResult(
            segments=[],
            engine_results={},
            overall_confidence=0.0,
        )

        tree = builder.build(
            result,
            original_text="",
            normalized_slp1="",
        )

        assert len(tree.parse_forest) == 0
        assert tree.best_parse is None

    def test_script_variants_generated(
        self,
        builder: TreeBuilder,
        ensemble_result: EnsembleResult,
    ) -> None:
        """Test that script variants are generated."""
        tree = builder.build(
            ensemble_result,
            original_text="rāmaḥ gacchati",
            normalized_slp1="rAmaH gacCati",
        )

        # Check tree-level scripts
        assert tree.scripts.slp1 == "rAmaH gacCati"
        assert tree.scripts.devanagari is not None
        assert tree.scripts.iast is not None

        # Check word-level scripts
        word = tree.all_words[0]
        assert word.scripts.slp1 == "rAma"

    def test_mode_preserved(
        self,
        builder: TreeBuilder,
        ensemble_result: EnsembleResult,
    ) -> None:
        """Test that mode is preserved."""
        tree = builder.build(
            ensemble_result,
            original_text="rāmaḥ gacchati",
            normalized_slp1="rAmaH gacCati",
            mode="educational",
        )

        assert tree.mode == "educational"

    def test_cache_tier_default(
        self,
        builder: TreeBuilder,
        ensemble_result: EnsembleResult,
    ) -> None:
        """Test that cache tier defaults to NONE."""
        tree = builder.build(
            ensemble_result,
            original_text="rāmaḥ gacchati",
            normalized_slp1="rAmaH gacCati",
        )

        assert tree.cached_at == CacheTier.NONE

    def test_unique_ids_generated(self, builder: TreeBuilder) -> None:
        """Test that unique IDs are generated."""
        segments = [
            MergedSegment(
                surface="test",
                lemma="test",
                confidence=0.9,
                engine_votes={"test": 0.9},
                agreement_score=0.9,
            ),
        ]

        result1 = EnsembleResult(
            segments=segments,
            engine_results={},
            overall_confidence=0.9,
        )
        result2 = EnsembleResult(
            segments=segments,
            engine_results={},
            overall_confidence=0.9,
        )

        tree1 = builder.build(result1, "test", "test")
        tree2 = builder.build(result2, "test", "test")

        # Sentence IDs share prefix but have unique suffix
        assert tree1.sentence_id.startswith("sent_")
        assert tree2.sentence_id.startswith("sent_")
        assert tree1.sentence_id != tree2.sentence_id

        # Parse IDs are unique
        if tree1.best_parse and tree2.best_parse:
            assert tree1.best_parse.parse_id != tree2.best_parse.parse_id

    def test_config_disables_dhatu_lookup(self) -> None:
        """Test that config can disable dhatu lookup."""
        config = TreeBuilderConfig(lookup_dhatus=False)
        builder = TreeBuilder(config)

        segments = [
            MergedSegment(
                surface="gacCati",
                lemma="gam",
                morphology="verb.third.singular.present",
                confidence=0.9,
                pos="verb",
                engine_votes={"test": 0.9},
                agreement_score=0.9,
            ),
        ]

        result = EnsembleResult(
            segments=segments,
            engine_results={},
            overall_confidence=0.9,
        )

        tree = builder.build(result, "gacchati", "gacCati")
        word = tree.all_words[0]

        # Dhatu should not be looked up
        assert word.dhatu is None

    def test_config_disables_meanings(self) -> None:
        """Test that config can disable meanings."""
        config = TreeBuilderConfig(generate_meanings=False)
        builder = TreeBuilder(config)

        segments = [
            MergedSegment(
                surface="rAmaH",
                lemma="rAma",
                confidence=0.9,
                pos="noun",
                meanings=["Rama", "pleasing"],
                engine_votes={"test": 0.9},
                agreement_score=0.9,
            ),
        ]

        result = EnsembleResult(
            segments=segments,
            engine_results={},
            overall_confidence=0.9,
        )

        tree = builder.build(result, "rāmaḥ", "rAmaH")
        word = tree.all_words[0]

        # Meanings should not be included
        assert len(word.meanings) == 0

    def test_to_dict_serialization(
        self,
        builder: TreeBuilder,
        ensemble_result: EnsembleResult,
    ) -> None:
        """Test that tree can be serialized to dict."""
        tree = builder.build(
            ensemble_result,
            original_text="rāmaḥ gacchati",
            normalized_slp1="rAmaH gacCati",
        )

        tree_dict = tree.to_dict()

        assert "sentence_id" in tree_dict
        assert "original_text" in tree_dict
        assert "parses" in tree_dict
        assert len(tree_dict["parses"]) == 1

        parse_dict = tree_dict["parses"][0]
        assert "parse_id" in parse_dict
        assert "sandhi_groups" in parse_dict

    def test_engine_votes_preserved(
        self,
        builder: TreeBuilder,
        ensemble_result: EnsembleResult,
    ) -> None:
        """Test that engine votes are preserved in parse tree."""
        tree = builder.build(
            ensemble_result,
            original_text="rāmaḥ gacchati",
            normalized_slp1="rAmaH gacCati",
        )

        parse = tree.best_parse
        assert parse is not None
        assert "vidyut" in parse.engine_votes
        assert "dharmamitra" in parse.engine_votes


class TestMorphologyParsing:
    """Tests for morphology parsing."""

    @pytest.fixture
    def builder(self) -> TreeBuilder:
        return TreeBuilder()

    def test_parse_noun_morphology(self, builder: TreeBuilder) -> None:
        """Test parsing noun morphology."""
        morph = builder._parse_morphology(
            "noun.masculine.singular.nominative",
            "noun",
        )

        assert morph is not None
        assert morph.pos == PartOfSpeech.NOUN
        assert morph.gender == Gender.MASCULINE
        assert morph.number == Number.SINGULAR
        assert morph.case == Case.NOMINATIVE

    def test_parse_verb_morphology(self, builder: TreeBuilder) -> None:
        """Test parsing verb morphology."""
        morph = builder._parse_morphology(
            "third.singular.present.active",
            "verb",
        )

        assert morph is not None
        assert morph.pos == PartOfSpeech.VERB

    def test_parse_abbreviated_morphology(self, builder: TreeBuilder) -> None:
        """Test parsing abbreviated morphology tags."""
        morph = builder._parse_morphology(
            "mas.sg.nom",
            "noun",
        )

        assert morph is not None
        assert morph.gender == Gender.MASCULINE
        assert morph.number == Number.SINGULAR
        assert morph.case == Case.NOMINATIVE

    def test_parse_morphology_no_pos(self, builder: TreeBuilder) -> None:
        """Test parsing with no POS."""
        morph = builder._parse_morphology("masculine.singular", None)
        assert morph is None

    def test_parse_all_cases(self, builder: TreeBuilder) -> None:
        """Test parsing all cases."""
        cases = [
            ("nominative", Case.NOMINATIVE),
            ("accusative", Case.ACCUSATIVE),
            ("instrumental", Case.INSTRUMENTAL),
            ("dative", Case.DATIVE),
            ("ablative", Case.ABLATIVE),
            ("genitive", Case.GENITIVE),
            ("locative", Case.LOCATIVE),
            ("vocative", Case.VOCATIVE),
        ]

        for case_str, expected in cases:
            result = builder._parse_case(case_str)
            assert result == expected, f"Failed for {case_str}"

    def test_parse_all_genders(self, builder: TreeBuilder) -> None:
        """Test parsing all genders."""
        morph_m = builder._parse_morphology("masculine", "noun")
        morph_f = builder._parse_morphology("feminine", "noun")
        morph_n = builder._parse_morphology("neuter", "noun")

        assert morph_m is not None and morph_m.gender == Gender.MASCULINE
        assert morph_f is not None and morph_f.gender == Gender.FEMININE
        assert morph_n is not None and morph_n.gender == Gender.NEUTER


class TestDhatuLookup:
    """Tests for dhatu lookup functionality."""

    @pytest.fixture
    def builder(self) -> TreeBuilder:
        return TreeBuilder()

    def test_lookup_common_dhatu(self, builder: TreeBuilder) -> None:
        """Test lookup of common dhatus."""
        dhatu = builder._lookup_dhatu("gam")
        assert dhatu is not None
        assert dhatu.dhatu == "gam"
        assert "to go" in dhatu.meanings

    def test_lookup_kf_dhatu(self, builder: TreeBuilder) -> None:
        """Test lookup of kṛ dhatu."""
        dhatu = builder._lookup_dhatu("kf")
        assert dhatu is not None
        assert dhatu.gana == 8

    def test_lookup_unknown_dhatu(self, builder: TreeBuilder) -> None:
        """Test lookup of unknown dhatu."""
        dhatu = builder._lookup_dhatu("unknown_root")
        assert dhatu is None

    def test_is_verb_detection(self, builder: TreeBuilder) -> None:
        """Test verb detection."""
        from sanskrit_analyzer.models.morphology import MorphologicalTag, PartOfSpeech

        verb_morph = MorphologicalTag(pos=PartOfSpeech.VERB)
        noun_morph = MorphologicalTag(pos=PartOfSpeech.NOUN)

        assert builder._is_verb("verb", verb_morph) is True
        assert builder._is_verb("verb", None) is True
        assert builder._is_verb("noun", noun_morph) is False
        assert builder._is_verb(None, None) is False
