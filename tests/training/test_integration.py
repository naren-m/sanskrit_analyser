"""Integration tests for training data generation pipeline."""

import json
import tempfile
from pathlib import Path

import pytest

from sanskrit_analyzer.training.config import TrainingConfig
from sanskrit_analyzer.training.corpus_loader import CorpusLoader
from sanskrit_analyzer.training.data_generator import BatchAnalyzer, DisambiguationGenerator
from sanskrit_analyzer.training.format_converter import GrammarFormatConverter


class TestTrainingConfig:
    """Tests for TrainingConfig."""

    def test_default_config(self) -> None:
        """Test default configuration values."""
        config = TrainingConfig()
        assert config.min_confidence == 0.85
        assert config.max_examples == 0
        assert config.batch_size == 100

    def test_config_from_dict(self) -> None:
        """Test creating config from dictionary."""
        data = {"min_confidence": 0.9, "max_examples": 100}
        config = TrainingConfig.from_dict(data)
        assert config.min_confidence == 0.9
        assert config.max_examples == 100

    def test_output_paths(self) -> None:
        """Test output path generation."""
        config = TrainingConfig(output_dir=Path("/tmp/test"))
        assert config.grammar_output_path() == Path("/tmp/test/grammar_training.jsonl")
        assert config.disambig_output_path() == Path("/tmp/test/disambig_training.jsonl")


class TestPipelineIntegration:
    """Integration tests for the full pipeline."""

    def test_corpus_to_format_flow(self, tmp_path: Path) -> None:
        """Test corpus loading through format conversion."""
        # Create test corpus
        corpus_file = tmp_path / "test.txt"
        corpus_file.write_text("रामो वनं गच्छति\n", encoding="utf-8")

        # Load corpus
        loader = CorpusLoader(corpus_file, corpus_name="Test")
        entries = list(loader)
        assert len(entries) == 1

        # Create mock parse result
        mock_parse = {
            "sandhi_groups": [
                {
                    "surface_form": "रामो",
                    "base_words": [{"lemma": "राम", "pos": "noun"}],
                }
            ],
            "confidence": 0.9,
        }

        # Convert to training format
        converter = GrammarFormatConverter()
        example = converter.to_training_example(entries[0].text, mock_parse)

        assert example["input"] == "Parse: रामो वनं गच्छति"
        assert "sandhi_groups" in example["output"]

    def test_validation_flow(self, tmp_path: Path) -> None:
        """Test validation of generated training data."""
        converter = GrammarFormatConverter()

        # Valid example
        valid_output = {
            "sandhi_groups": [
                {
                    "surface_form": "रामः",
                    "base_words": [{"lemma": "राम", "morphology": "noun-nom-sg-m"}],
                }
            ],
        }
        errors = converter.validate_output(valid_output)
        assert len(errors) == 0

        # Invalid example
        invalid_output = {"sandhi_groups": [{"surface_form": "test"}]}
        errors = converter.validate_output(invalid_output)
        assert len(errors) > 0

    def test_jsonl_output_format(self, tmp_path: Path) -> None:
        """Test that output is valid JSONL."""
        output_file = tmp_path / "output.jsonl"

        # Write some examples
        examples = [
            {"input": "Parse: test1", "output": {"sandhi_groups": []}},
            {"input": "Parse: test2", "output": {"sandhi_groups": []}},
        ]

        with open(output_file, "w", encoding="utf-8") as f:
            for ex in examples:
                f.write(json.dumps(ex, ensure_ascii=False) + "\n")

        # Read and verify
        with open(output_file, encoding="utf-8") as f:
            lines = f.readlines()
            assert len(lines) == 2
            for line in lines:
                parsed = json.loads(line)
                assert "input" in parsed
                assert "output" in parsed


class TestDisambiguationGenerator:
    """Tests for DisambiguationGenerator."""

    def test_generate_example(self) -> None:
        """Test generating a disambiguation example."""
        generator = DisambiguationGenerator()

        parses = [
            {"interpretation": "Rama goes", "confidence": 0.9},
            {"interpretation": "Go Rama", "confidence": 0.7},
        ]

        example = generator.generate_example(
            text="रामो गच्छति",
            parses=parses,
            selected_index=0,
            context="narrative",
        )

        assert example["input"]["text"] == "रामो गच्छति"
        assert len(example["input"]["parses"]) == 2
        assert example["output"]["selected"] == 0
        assert "reasoning" in example["output"]


class TestSampleCorpusIntegration:
    """Integration tests with sample corpus files."""

    def test_sample_ramayana_format(self) -> None:
        """Test that sample Ramayana verses can be loaded and formatted."""
        corpus_path = Path("sanskrit_analyzer/data/corpora/sample_ramayana.txt")
        if not corpus_path.exists():
            pytest.skip("Sample corpus not available")

        loader = CorpusLoader(corpus_path, corpus_name="Ramayana")
        converter = GrammarFormatConverter()

        for entry in list(loader)[:5]:  # Test first 5 entries
            # Verify entry can be used in training example
            mock_parse = {"sandhi_groups": [], "confidence": 0.5}
            example = converter.to_training_example(entry.text, mock_parse)

            assert example["input"].startswith("Parse: ")
            assert entry.metadata.corpus == "Ramayana"
