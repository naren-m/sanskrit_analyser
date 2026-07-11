"""Tests for format converters."""

import pytest

from sanskrit_analyzer.training.format_converter import (
    DisambiguationFormatConverter,
    GrammarFormatConverter,
)
from sanskrit_analyzer.training.reasoning_templates import (
    REASONING_TEMPLATES,
    fill_template,
    generate_case_agreement_reasoning,
    generate_verb_agreement_reasoning,
    generate_sandhi_reasoning,
    generate_semantic_reasoning,
    detect_applicable_rule,
)


class TestGrammarFormatConverter:
    """Tests for GrammarFormatConverter."""

    def test_convert_simple_parse(self) -> None:
        """Test converting a simple parse result."""
        converter = GrammarFormatConverter()

        parse_result = {
            "sandhi_groups": [
                {
                    "surface_form": "रामो",
                    "base_words": [
                        {"lemma": "राम", "pos": "noun", "case": "nom", "number": "sg", "gender": "m"}
                    ],
                }
            ],
            "confidence": 0.95,
        }

        output = converter.convert(parse_result)

        assert "sandhi_groups" in output
        assert len(output["sandhi_groups"]) == 1
        assert output["sandhi_groups"][0]["surface_form"] == "रामो"
        assert output["sandhi_groups"][0]["base_words"][0]["lemma"] == "राम"
        assert "noun-nom-sg-m" in output["sandhi_groups"][0]["base_words"][0]["morphology"]
        assert output["confidence"] == 0.95

    def test_convert_verb_with_dhatu(self) -> None:
        """Test converting a verb with dhatu information."""
        converter = GrammarFormatConverter()

        parse_result = {
            "sandhi_groups": [
                {
                    "surface_form": "गच्छति",
                    "base_words": [
                        {
                            "lemma": "गम्",
                            "pos": "verb",
                            "person": "3",
                            "number": "sg",
                            "tense": "pres",
                            "voice": "act",
                            "dhatu": "गम्",
                        }
                    ],
                }
            ],
        }

        output = converter.convert(parse_result)

        word = output["sandhi_groups"][0]["base_words"][0]
        assert "√गम्" in word.get("dhatu", "")

    def test_convert_empty_parse(self) -> None:
        """Test converting an empty parse result."""
        converter = GrammarFormatConverter()

        output = converter.convert({})

        assert output["sandhi_groups"] == []

    def test_to_training_example(self) -> None:
        """Test creating a complete training example."""
        converter = GrammarFormatConverter()

        parse_result = {
            "sandhi_groups": [
                {"surface_form": "रामः", "base_words": [{"lemma": "राम"}]}
            ],
        }

        example = converter.to_training_example("रामः", parse_result)

        assert example["input"] == "Parse: रामः"
        assert "output" in example
        assert "sandhi_groups" in example["output"]


class TestGrammarValidation:
    """Tests for grammar output validation."""

    def test_validate_valid_output(self) -> None:
        """Test validation of valid output."""
        converter = GrammarFormatConverter()

        output = {
            "sandhi_groups": [
                {
                    "surface_form": "रामः",
                    "base_words": [{"lemma": "राम", "morphology": "noun-nom-sg-m"}],
                }
            ],
        }

        errors = converter.validate_output(output)
        assert len(errors) == 0

    def test_validate_missing_sandhi_groups(self) -> None:
        """Test validation catches missing sandhi_groups."""
        converter = GrammarFormatConverter()

        errors = converter.validate_output({})
        assert any("sandhi_groups" in e for e in errors)

    def test_validate_missing_surface_form(self) -> None:
        """Test validation catches missing surface_form."""
        converter = GrammarFormatConverter()

        output = {"sandhi_groups": [{"base_words": []}]}
        errors = converter.validate_output(output)
        assert any("surface_form" in e for e in errors)

    def test_validate_missing_lemma(self) -> None:
        """Test validation catches missing lemma in base_words."""
        converter = GrammarFormatConverter()

        output = {
            "sandhi_groups": [
                {"surface_form": "test", "base_words": [{"morphology": "noun"}]}
            ]
        }
        errors = converter.validate_output(output)
        assert any("lemma" in e for e in errors)


class TestReasoningTemplates:
    """Tests for reasoning templates."""

    def test_all_templates_exist(self) -> None:
        """Test that all expected templates exist."""
        expected = [
            "case_agreement",
            "verb_agreement",
            "sandhi_preference",
            "semantic_coherence",
        ]
        for template in expected:
            assert template in REASONING_TEMPLATES

    def test_fill_template_case_agreement(self) -> None:
        """Test filling case agreement template."""
        reasoning = fill_template(
            "case_agreement",
            nominative="रामः",
            nom_case="nominative",
            verb="गच्छति",
            alternative="रामम्",
            wrong_case="accusative",
        )

        assert "रामः" in reasoning
        assert "गच्छति" in reasoning
        assert "nominative" in reasoning

    def test_fill_template_unknown_raises(self) -> None:
        """Test that unknown template raises KeyError."""
        with pytest.raises(KeyError):
            fill_template("nonexistent_template")

    def test_generate_case_agreement_reasoning(self) -> None:
        """Test case agreement reasoning generator."""
        reasoning = generate_case_agreement_reasoning(
            nominative="रामः",
            verb="गच्छति",
            alternative="रामम्",
            wrong_case="accusative",
        )

        assert "case_agreement" in reasoning
        assert "रामः" in reasoning

    def test_generate_verb_agreement_reasoning(self) -> None:
        """Test verb agreement reasoning generator."""
        reasoning = generate_verb_agreement_reasoning(
            verb="गच्छति",
            person="third",
            number="singular",
            expected_subject="he/she/it",
            parse_issue="Parse 1 has first-person subject",
        )

        assert "verb_agreement" in reasoning
        assert "गच्छति" in reasoning

    def test_generate_sandhi_reasoning(self) -> None:
        """Test sandhi reasoning generator."""
        reasoning = generate_sandhi_reasoning(
            preferred_split="राम + ओ",
            sandhi_type="vowel",
            alternative_split="रामो",
        )

        assert "sandhi_preference" in reasoning

    def test_generate_semantic_reasoning(self) -> None:
        """Test semantic reasoning generator."""
        reasoning = generate_semantic_reasoning(
            selected_meaning="Rama goes to the forest",
            context="narrative about exile",
            alternative_meaning="The forest goes to Rama",
        )

        assert "semantic_coherence" in reasoning

    def test_detect_applicable_rule_single_parse(self) -> None:
        """Test rule detection with single parse."""
        parses = [{"interpretation": "Only parse", "confidence": 0.9}]
        rule_name, params = detect_applicable_rule(parses, 0)

        assert rule_name == "semantic_coherence"

    def test_detect_applicable_rule_multiple_parses(self) -> None:
        """Test rule detection with multiple parses."""
        parses = [
            {"interpretation": "Parse 0", "confidence": 0.9},
            {"interpretation": "Parse 1", "confidence": 0.7},
        ]
        rule_name, params = detect_applicable_rule(parses, 0)

        assert rule_name in REASONING_TEMPLATES
        assert isinstance(params, dict)

    def test_detect_applicable_rule_case_disagreement(self) -> None:
        """Differing case between parses selects the case_agreement rule."""
        parses = [
            {"interpretation": "Rama (subject)", "case": "nom", "verb": "gacchati"},
            {"interpretation": "Rama (object)", "case": "acc"},
        ]
        rule_name, params = detect_applicable_rule(parses, 0)

        assert rule_name == "case_agreement"
        assert params["nom_case"] == "nom"
        assert params["wrong_case"] == "acc"
        # Params must actually fill the template without missing keys.
        assert fill_template(rule_name, **params)

    def test_detect_applicable_rule_verb_disagreement(self) -> None:
        """Differing person/number selects the verb_agreement rule."""
        parses = [
            {"interpretation": "he goes", "person": "third", "number": "singular"},
            {"interpretation": "they go", "person": "third", "number": "plural"},
        ]
        rule_name, params = detect_applicable_rule(parses, 0)

        assert rule_name == "verb_agreement"
        assert fill_template(rule_name, **params)

    def test_detect_applicable_rule_gender_disagreement(self) -> None:
        """Differing gender selects the gender_agreement rule."""
        parses = [
            {"interpretation": "beautiful (f)", "gender": "f"},
            {"interpretation": "beautiful (m)", "gender": "m"},
        ]
        rule_name, params = detect_applicable_rule(parses, 0)

        assert rule_name == "gender_agreement"
        assert fill_template(rule_name, **params)

    def test_detect_applicable_rule_sandhi_disagreement(self) -> None:
        """Differing segmentation selects the sandhi_preference rule."""
        parses = [
            {"interpretation": "A", "segments": ["yoga", "sUtra"]},
            {"interpretation": "B", "segments": ["yo", "gasUtra"]},
        ]
        rule_name, params = detect_applicable_rule(parses, 0)

        assert rule_name == "sandhi_preference"
        assert fill_template(rule_name, **params)

    def test_detect_applicable_rule_varies_with_input(self) -> None:
        """Different inputs must yield different rules (not one constant)."""
        case_rule, _ = detect_applicable_rule(
            [{"case": "nom"}, {"case": "acc"}], 0
        )
        verb_rule, _ = detect_applicable_rule(
            [{"number": "singular"}, {"number": "plural"}], 0
        )
        gender_rule, _ = detect_applicable_rule(
            [{"gender": "m"}, {"gender": "f"}], 0
        )

        assert len({case_rule, verb_rule, gender_rule}) == 3


class TestDisambiguationFormatConverter:
    """Tests for DisambiguationFormatConverter."""

    def test_convert_produces_output_shape(self) -> None:
        """convert() returns selected/reasoning/confidence."""
        converter = DisambiguationFormatConverter()
        parses = [
            {"interpretation": "Rama (subject)", "case": "nom", "confidence": 0.9},
            {"interpretation": "Rama (object)", "case": "acc", "confidence": 0.6},
        ]

        output = converter.convert(parses, 0)

        assert output["selected"] == 0
        assert isinstance(output["reasoning"], str) and output["reasoning"]
        assert output["confidence"] == 0.9

    def test_to_training_example(self) -> None:
        """to_training_example() builds a full input/output example."""
        converter = DisambiguationFormatConverter()
        parses = [
            {"interpretation": "he goes", "number": "singular", "confidence": 0.8},
            {"interpretation": "they go", "number": "plural", "confidence": 0.5},
        ]

        example = converter.to_training_example(
            "gacchati", parses, 0, context="narrative"
        )

        assert example["input"]["text"] == "gacchati"
        assert len(example["input"]["parses"]) == 2
        assert example["input"]["context"] == "narrative"
        assert example["output"]["selected"] == 0
        assert converter.validate_output(example["output"]) == []

    def test_validate_output_catches_missing_fields(self) -> None:
        """validate_output() flags missing required fields."""
        converter = DisambiguationFormatConverter()
        errors = converter.validate_output({"selected": 0})
        assert any("reasoning" in e for e in errors)
        assert any("confidence" in e for e in errors)
