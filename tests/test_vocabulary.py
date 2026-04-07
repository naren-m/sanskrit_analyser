"""Tests for vocabulary loading and lookup."""

from pathlib import Path

import pytest

from sanskrit_analyzer.validation.vocabulary import Vocabulary


class TestVocabularyLoadDefault:
    """Tests for loading the default vocabulary file."""

    def test_load_default_returns_vocabulary(self) -> None:
        """Loading default vocabulary returns a Vocabulary instance."""
        vocab = Vocabulary.load_default()
        assert isinstance(vocab, Vocabulary)

    def test_load_default_has_entries(self) -> None:
        """Default vocabulary contains entries."""
        vocab = Vocabulary.load_default()
        assert len(vocab) > 0

    def test_load_default_has_expected_count(self) -> None:
        """Default vocabulary has at least 80 entries."""
        vocab = Vocabulary.load_default()
        assert len(vocab) >= 80


class TestVocabularyLookup:
    """Tests for looking up words in vocabulary."""

    @pytest.fixture()
    def vocab(self) -> Vocabulary:
        """Load the default vocabulary for lookup tests."""
        return Vocabulary.load_default()

    def test_contains_known_word(self, vocab: Vocabulary) -> None:
        """Known SLP1 word is found in vocabulary."""
        assert vocab.contains("yoga") is True

    def test_contains_known_word_citta(self, vocab: Vocabulary) -> None:
        """Another known SLP1 word (citta) is found."""
        assert vocab.contains("citta") is True

    def test_contains_known_indeclinable(self, vocab: Vocabulary) -> None:
        """Known indeclinable (aTa) is found."""
        assert vocab.contains("aTa") is True

    def test_does_not_contain_unknown_word(self, vocab: Vocabulary) -> None:
        """Unknown word returns False."""
        assert vocab.contains("xyznonexistent") is False

    def test_does_not_contain_empty_string(self, vocab: Vocabulary) -> None:
        """Empty string returns False."""
        assert vocab.contains("") is False


class TestVocabularyIndeclinables:
    """Tests for indeclinable identification."""

    @pytest.fixture()
    def vocab(self) -> Vocabulary:
        """Load the default vocabulary."""
        return Vocabulary.load_default()

    def test_atha_is_indeclinable(self, vocab: Vocabulary) -> None:
        """aTa (atha) is identified as indeclinable."""
        assert vocab.is_indeclinable("aTa") is True

    def test_ca_is_indeclinable(self, vocab: Vocabulary) -> None:
        """ca is identified as indeclinable."""
        assert vocab.is_indeclinable("ca") is True

    def test_eva_is_indeclinable(self, vocab: Vocabulary) -> None:
        """eva is identified as indeclinable."""
        assert vocab.is_indeclinable("eva") is True

    def test_yoga_is_not_indeclinable(self, vocab: Vocabulary) -> None:
        """yoga is a noun, not indeclinable."""
        assert vocab.is_indeclinable("yoga") is False

    def test_unknown_word_is_not_indeclinable(self, vocab: Vocabulary) -> None:
        """Unknown word is not indeclinable."""
        assert vocab.is_indeclinable("xyznonexistent") is False


class TestVocabularyFromFile:
    """Tests for loading vocabulary from a custom file."""

    def test_from_file_loads_correctly(self, tmp_path: Path) -> None:
        """Loading from a custom file works."""
        vocab_file = tmp_path / "custom_vocab.json"
        vocab_file.write_text(
            '{"version": "1.0", "description": "test", "words": ['
            '{"lemma": "deva", "slp1": "deva", "type": "noun", "indeclinable": false}'
            "]}"
        )
        vocab = Vocabulary.from_file(vocab_file)
        assert len(vocab) == 1
        assert vocab.contains("deva") is True

    def test_from_file_missing_raises(self, tmp_path: Path) -> None:
        """Loading from a missing file raises FileNotFoundError."""
        missing = tmp_path / "missing.json"
        with pytest.raises(FileNotFoundError):
            Vocabulary.from_file(missing)

    def test_from_file_invalid_json_raises(self, tmp_path: Path) -> None:
        """Loading from an invalid JSON file raises ValueError."""
        bad_file = tmp_path / "bad.json"
        bad_file.write_text("not json at all")
        with pytest.raises(ValueError, match="Invalid JSON"):
            Vocabulary.from_file(bad_file)

    def test_from_file_missing_words_key_raises(self, tmp_path: Path) -> None:
        """Loading a file without 'words' key raises ValueError."""
        bad_file = tmp_path / "no_words.json"
        bad_file.write_text('{"version": "1.0"}')
        with pytest.raises(ValueError, match="words"):
            Vocabulary.from_file(bad_file)

    def test_from_file_entry_missing_slp1_raises(self, tmp_path: Path) -> None:
        """An entry without 'slp1' key raises ValueError."""
        bad_file = tmp_path / "no_slp1.json"
        bad_file.write_text(
            '{"words": [{"lemma": "test", "type": "noun", "indeclinable": false}]}'
        )
        with pytest.raises(ValueError, match="slp1"):
            Vocabulary.from_file(bad_file)

    def test_from_file_accepts_string_path(self, tmp_path: Path) -> None:
        """from_file should accept a string path."""
        vocab_file = tmp_path / "str_path.json"
        vocab_file.write_text(
            '{"words": [{"lemma": "test", "slp1": "test", "type": "noun", "indeclinable": false}]}'
        )
        vocab = Vocabulary.from_file(str(vocab_file))
        assert len(vocab) == 1


class TestVocabularyEmpty:
    """Tests for empty vocabulary behavior."""

    def test_empty_vocabulary(self) -> None:
        """An empty vocabulary has zero length."""
        vocab = Vocabulary(words={}, indeclinables=set())
        assert len(vocab) == 0

    def test_empty_vocabulary_contains_nothing(self) -> None:
        """Empty vocabulary contains no words."""
        vocab = Vocabulary(words={}, indeclinables=set())
        assert vocab.contains("yoga") is False

    def test_empty_vocabulary_no_indeclinables(self) -> None:
        """Empty vocabulary has no indeclinables."""
        vocab = Vocabulary(words={}, indeclinables=set())
        assert vocab.is_indeclinable("ca") is False
