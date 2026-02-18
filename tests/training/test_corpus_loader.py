"""Tests for corpus loading utilities."""

import json
import tempfile
from pathlib import Path

import pytest

from sanskrit_analyzer.training.corpus_loader import CorpusLoader, CorpusEntry, VerseMetadata


class TestCorpusLoaderText:
    """Tests for loading text files."""

    def test_load_simple_text_file(self, tmp_path: Path) -> None:
        """Test loading a simple text file with one sentence per line."""
        corpus_file = tmp_path / "test.txt"
        corpus_file.write_text("रामो वनं गच्छति\nसीता रामं अनुगच्छति\n", encoding="utf-8")

        loader = CorpusLoader(corpus_file, corpus_name="Test")
        entries = list(loader)

        assert len(entries) == 2
        assert entries[0].text == "रामो वनं गच्छति"
        assert entries[1].text == "सीता रामं अनुगच्छति"

    def test_skip_empty_lines(self, tmp_path: Path) -> None:
        """Test that empty lines are skipped."""
        corpus_file = tmp_path / "test.txt"
        corpus_file.write_text("Line 1\n\nLine 2\n\n\nLine 3\n", encoding="utf-8")

        loader = CorpusLoader(corpus_file)
        entries = list(loader)

        assert len(entries) == 3

    def test_skip_comment_lines(self, tmp_path: Path) -> None:
        """Test that comment lines (starting with #) are skipped."""
        corpus_file = tmp_path / "test.txt"
        corpus_file.write_text("# This is a comment\nActual text\n# Another comment\n", encoding="utf-8")

        loader = CorpusLoader(corpus_file)
        entries = list(loader)

        assert len(entries) == 1
        assert entries[0].text == "Actual text"

    def test_metadata_tracking(self, tmp_path: Path) -> None:
        """Test that metadata is tracked correctly."""
        corpus_file = tmp_path / "ramayana.txt"
        corpus_file.write_text("Verse 1\nVerse 2\n", encoding="utf-8")

        loader = CorpusLoader(corpus_file, corpus_name="Ramayana", chapter="1")
        entries = list(loader)

        assert entries[0].metadata.corpus == "Ramayana"
        assert entries[0].metadata.chapter == "1"
        assert entries[0].metadata.verse == 1
        assert entries[1].metadata.verse == 2
        assert str(corpus_file) in entries[0].metadata.source_file


class TestCorpusLoaderJSON:
    """Tests for loading JSON files."""

    def test_load_simple_json_list(self, tmp_path: Path) -> None:
        """Test loading a JSON file with simple list of strings."""
        corpus_file = tmp_path / "test.json"
        data = ["First verse", "Second verse"]
        corpus_file.write_text(json.dumps(data), encoding="utf-8")

        loader = CorpusLoader(corpus_file)
        entries = list(loader)

        assert len(entries) == 2
        assert entries[0].text == "First verse"

    def test_load_json_with_objects(self, tmp_path: Path) -> None:
        """Test loading a JSON file with object entries."""
        corpus_file = tmp_path / "test.json"
        data = [
            {"text": "Verse 1", "chapter": "1"},
            {"verse": "Verse 2", "chapter": "2"},
        ]
        corpus_file.write_text(json.dumps(data), encoding="utf-8")

        loader = CorpusLoader(corpus_file)
        entries = list(loader)

        assert len(entries) == 2
        assert entries[0].text == "Verse 1"
        assert entries[0].metadata.chapter == "1"
        assert entries[1].text == "Verse 2"
        assert entries[1].metadata.chapter == "2"

    def test_load_structured_json(self, tmp_path: Path) -> None:
        """Test loading a JSON file with structured format."""
        corpus_file = tmp_path / "test.json"
        data = {
            "corpus": "Gita",
            "verses": [
                {"text": "धर्मक्षेत्रे", "chapter": "1"},
                {"text": "कुतस्त्वा", "chapter": "2"},
            ],
        }
        corpus_file.write_text(json.dumps(data), encoding="utf-8")

        loader = CorpusLoader(corpus_file)
        entries = list(loader)

        assert len(entries) == 2
        assert entries[0].metadata.corpus == "Gita"


class TestCorpusLoaderIterator:
    """Tests for iterator behavior."""

    def test_len_returns_entry_count(self, tmp_path: Path) -> None:
        """Test that len() returns the number of entries."""
        corpus_file = tmp_path / "test.txt"
        corpus_file.write_text("Line 1\nLine 2\nLine 3\n", encoding="utf-8")

        loader = CorpusLoader(corpus_file)
        assert len(loader) == 3

    def test_multiple_iterations(self, tmp_path: Path) -> None:
        """Test that corpus can be iterated multiple times."""
        corpus_file = tmp_path / "test.txt"
        corpus_file.write_text("Line 1\nLine 2\n", encoding="utf-8")

        loader = CorpusLoader(corpus_file)
        first_pass = list(loader)
        second_pass = list(loader)

        assert first_pass == second_pass

    def test_entries_property(self, tmp_path: Path) -> None:
        """Test the entries property returns all entries."""
        corpus_file = tmp_path / "test.txt"
        corpus_file.write_text("Line 1\nLine 2\n", encoding="utf-8")

        loader = CorpusLoader(corpus_file)
        assert len(loader.entries) == 2

    def test_file_not_found_raises_error(self, tmp_path: Path) -> None:
        """Test that loading nonexistent file raises FileNotFoundError."""
        loader = CorpusLoader(tmp_path / "nonexistent.txt")
        with pytest.raises(FileNotFoundError):
            loader.load()


class TestSampleCorpora:
    """Tests for sample corpus files."""

    def test_sample_ramayana_loads(self) -> None:
        """Test that sample Ramayana corpus loads successfully."""
        corpus_path = Path("sanskrit_analyzer/data/corpora/sample_ramayana.txt")
        if corpus_path.exists():
            loader = CorpusLoader(corpus_path, corpus_name="Ramayana")
            entries = list(loader)
            assert len(entries) > 0

    def test_sample_gita_loads(self) -> None:
        """Test that sample Gita corpus loads successfully."""
        corpus_path = Path("sanskrit_analyzer/data/corpora/sample_gita.txt")
        if corpus_path.exists():
            loader = CorpusLoader(corpus_path, corpus_name="Gita")
            entries = list(loader)
            assert len(entries) > 0
