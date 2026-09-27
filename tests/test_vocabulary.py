"""Tests for vocabulary loading and lookup."""

import json
from pathlib import Path

import pytest

from sanskrit_analyzer.validation.vocabulary import Vocabulary
from tests._cases import check_cases

DEFAULT = Vocabulary.load_default()
EMPTY = Vocabulary(words={}, indeclinables=set())


def test_load_default_has_expected_count() -> None:
    assert isinstance(DEFAULT, Vocabulary)
    assert len(DEFAULT) >= 80
    assert len(EMPTY) == 0


# (id, vocabulary, SLP1 word, contains, is_indeclinable)
LOOKUP_CASES = [
    ("default-yoga-noun-known-not-avyaya", DEFAULT, "yoga", True, False),
    ("default-citta-known", DEFAULT, "citta", True, None),
    ("default-aTa-known-and-avyaya", DEFAULT, "aTa", True, True),
    ("default-ca-avyaya", DEFAULT, "ca", None, True),
    ("default-eva-avyaya", DEFAULT, "eva", None, True),
    ("default-unknown-word", DEFAULT, "xyznonexistent", False, False),
    ("default-empty-string", DEFAULT, "", False, None),
    ("empty-vocab-contains-nothing", EMPTY, "yoga", False, None),
    ("empty-vocab-no-avyaya", EMPTY, "ca", None, False),
]


def test_lookup() -> None:
    def check(vocab, word, contains, indeclinable):
        if contains is not None:
            assert vocab.contains(word) is contains
        if indeclinable is not None:
            assert vocab.is_indeclinable(word) is indeclinable

    check_cases(LOOKUP_CASES, check)


def _entry(**kw) -> dict:
    return {"lemma": "test", "slp1": "test", "type": "noun", "indeclinable": False, **kw}


# (id, file text or None for a missing file, expected exception or None,
#  match, words the loaded vocab must contain)
FROM_FILE_CASES = [
    ("loads-custom-file",
     json.dumps({"version": "1.0", "description": "test", "words": [_entry(slp1="deva")]}),
     None, None, ["deva"]),
    ("missing-file-raises", None, FileNotFoundError, None, []),
    ("invalid-json-raises", "not json at all", ValueError, "Invalid JSON", []),
    ("missing-words-key-raises", '{"version": "1.0"}', ValueError, "words", []),
    ("entry-missing-slp1-raises",
     json.dumps({"words": [{"lemma": "test", "type": "noun", "indeclinable": False}]}),
     ValueError, "slp1", []),
]


def test_from_file(tmp_path: Path) -> None:
    def check(text, exc, match, words):
        path = tmp_path / "vocab.json"
        path.unlink(missing_ok=True)
        if text is not None:
            path.write_text(text)
        if exc is not None:
            with pytest.raises(exc, match=match):
                Vocabulary.from_file(path)
            return
        vocab = Vocabulary.from_file(path)
        assert len(vocab) == len(words)
        assert all(vocab.contains(w) for w in words)

    check_cases(FROM_FILE_CASES, check)


def test_from_file_accepts_string_path(tmp_path: Path) -> None:
    vocab_file = tmp_path / "str_path.json"
    vocab_file.write_text(json.dumps({"words": [_entry()]}))
    assert len(Vocabulary.from_file(str(vocab_file))) == 1
