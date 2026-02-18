"""Tests for format converters."""

import pytest

from sanskrit_analyzer.training.format_converter import GrammarFormatConverter
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
