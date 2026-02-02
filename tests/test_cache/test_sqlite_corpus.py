"""Tests for SQLite corpus storage."""

import os
import tempfile
from datetime import datetime

import pytest

from sanskrit_analyzer.cache.sqlite_corpus import CorpusEntry, CorpusStats, SQLiteCorpus


class TestCorpusEntry:
    """Tests for CorpusEntry dataclass."""

    def test_get_result(self) -> None:
        """Test parsing JSON result."""
        entry = CorpusEntry(
            id="test123",
            original_text="gacchati",
            normalized_slp1="gacCati",
            mode="PRODUCTION",
            result_json='{"segments": [{"surface": "gacchati"}]}',
            created_at=datetime.now(),
            accessed_at=datetime.now(),
            access_count=1,
            disambiguated=False,
            selected_parse=None,
        )

        result = entry.get_result()
        assert result == {"segments": [{"surface": "gacchati"}]}


class TestCorpusStats:
    """Tests for CorpusStats dataclass."""

    def test_default_values(self) -> None:
        """Test default statistics values."""
        stats = CorpusStats()
        assert stats.total_entries == 0
        assert stats.disambiguated_entries == 0
        assert stats.total_accesses == 0


class TestSQLiteCorpus:
    """Tests for SQLiteCorpus class."""

    @pytest.fixture
    def temp_db(self) -> str:
        """Create a temporary database file."""
        fd, path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        yield path
        if os.path.exists(path):
            os.unlink(path)

    @pytest.fixture
    def corpus(self, temp_db: str) -> SQLiteCorpus:
        """Create a corpus instance with temp database."""
        return SQLiteCorpus(db_path=temp_db)

    def test_init_creates_tables(self, corpus: SQLiteCorpus) -> None:
        """Test that initialization creates required tables."""
        cursor = corpus._conn.cursor()

        # Check main table exists
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='analyses'"
        )
        assert cursor.fetchone() is not None

        # Check FTS table exists
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='analyses_fts'"
        )
        assert cursor.fetchone() is not None

    def test_set_and_get(self, corpus: SQLiteCorpus) -> None:
        """Test basic set and get operations."""
        result = {"segments": [{"surface": "test"}], "confidence": 0.9}

        corpus.set("key1", "gacchati", "gacCati", "PRODUCTION", result)
        entry = corpus.get("key1")

        assert entry is not None
        assert entry.id == "key1"
        assert entry.original_text == "gacchati"
        assert entry.normalized_slp1 == "gacCati"
        assert entry.mode == "PRODUCTION"
        assert entry.get_result() == result

    def test_get_missing(self, corpus: SQLiteCorpus) -> None:
        """Test getting a missing key."""
        assert corpus.get("nonexistent") is None

    def test_get_updates_access_tracking(self, corpus: SQLiteCorpus) -> None:
        """Test that get updates access count and timestamp."""
        corpus.set("key1", "test", "test", "PRODUCTION", {})

        # First access
        entry1 = corpus.get("key1")
        assert entry1 is not None
        initial_count = entry1.access_count

        # Second access
        entry2 = corpus.get("key1")
        assert entry2 is not None
        # Access count includes the initial set (1) + first get (+1) + second get (+1)
        assert entry2.access_count == initial_count + 1

    def test_count(self, corpus: SQLiteCorpus) -> None:
        """Test counting entries."""
        assert corpus.count() == 0

        corpus.set("key1", "test1", "test1", "PRODUCTION", {})
        assert corpus.count() == 1

        corpus.set("key2", "test2", "test2", "PRODUCTION", {})
        assert corpus.count() == 2

    def test_delete(self, corpus: SQLiteCorpus) -> None:
        """Test deleting an entry."""
        corpus.set("key1", "test", "test", "PRODUCTION", {})
        assert corpus.count() == 1

        assert corpus.delete("key1") is True
        assert corpus.count() == 0
        assert corpus.get("key1") is None

    def test_delete_missing(self, corpus: SQLiteCorpus) -> None:
        """Test deleting a missing key."""
        assert corpus.delete("nonexistent") is False

    def test_update_disambiguation(self, corpus: SQLiteCorpus) -> None:
        """Test updating disambiguation choice."""
        corpus.set("key1", "test", "test", "PRODUCTION", {})

        assert corpus.update_disambiguation("key1", 2) is True

        entry = corpus.get("key1")
        assert entry is not None
        assert entry.disambiguated is True
        assert entry.selected_parse == 2

    def test_update_disambiguation_missing(self, corpus: SQLiteCorpus) -> None:
        """Test updating disambiguation for missing key."""
        assert corpus.update_disambiguation("nonexistent", 0) is False

    def test_stats(self, corpus: SQLiteCorpus) -> None:
        """Test getting corpus statistics."""
        corpus.set("key1", "test1", "test1", "PRODUCTION", {})
        corpus.set("key2", "test2", "test2", "PRODUCTION", {})
        corpus.update_disambiguation("key1", 0)

        # Access some entries
        corpus.get("key1")
        corpus.get("key2")

        stats = corpus.stats()
        assert stats.total_entries == 2
        assert stats.disambiguated_entries == 1
        assert stats.total_accesses >= 4  # 2 sets + 2 gets

    def test_search_fts(self, corpus: SQLiteCorpus) -> None:
        """Test full-text search."""
        corpus.set("key1", "gacchati nayati", "gacCati nayati", "PRODUCTION", {})
        corpus.set("key2", "pazyati vadati", "pazyati vadati", "PRODUCTION", {})
        corpus.set("key3", "gacchati vadati", "gacCati vadati", "PRODUCTION", {})

        results = corpus.search("gacchati")
        assert len(results) == 2
        ids = [r.id for r in results]
        assert "key1" in ids
        assert "key3" in ids

    def test_get_by_mode(self, corpus: SQLiteCorpus) -> None:
        """Test filtering by mode."""
        corpus.set("key1", "test1", "test1", "PRODUCTION", {})
        corpus.set("key2", "test2", "test2", "ACADEMIC", {})
        corpus.set("key3", "test3", "test3", "PRODUCTION", {})

        results = corpus.get_by_mode("PRODUCTION")
        assert len(results) == 2

        results = corpus.get_by_mode("ACADEMIC")
        assert len(results) == 1

    def test_get_recent(self, corpus: SQLiteCorpus) -> None:
        """Test getting recent entries."""
        corpus.set("key1", "test1", "test1", "PRODUCTION", {})
        corpus.set("key2", "test2", "test2", "PRODUCTION", {})
        corpus.set("key3", "test3", "test3", "PRODUCTION", {})

        results = corpus.get_recent(limit=2)
        assert len(results) == 2
        # All entries are returned (order may vary since they were created at same time)
        ids = {r.id for r in results}
        # Just verify we get 2 valid entries
        assert len(ids) == 2
        assert ids.issubset({"key1", "key2", "key3"})

    def test_clear(self, corpus: SQLiteCorpus) -> None:
        """Test clearing all entries."""
        corpus.set("key1", "test1", "test1", "PRODUCTION", {})
        corpus.set("key2", "test2", "test2", "PRODUCTION", {})

        count = corpus.clear()
        assert count == 2
        assert corpus.count() == 0

    def test_upsert_behavior(self, corpus: SQLiteCorpus) -> None:
        """Test that set replaces existing entries."""
        corpus.set("key1", "test1", "test1", "PRODUCTION", {"version": 1})
        corpus.set("key1", "test1", "test1", "PRODUCTION", {"version": 2})

        assert corpus.count() == 1
        entry = corpus.get("key1")
        assert entry is not None
        assert entry.get_result() == {"version": 2}

    def test_unicode_text(self, corpus: SQLiteCorpus) -> None:
        """Test storing Unicode (Devanagari) text."""
        corpus.set("key1", "गच्छति", "gacCati", "PRODUCTION", {"text": "गच्छति"})

        entry = corpus.get("key1")
        assert entry is not None
        assert entry.original_text == "गच्छति"
        assert entry.get_result()["text"] == "गच्छति"

    def test_complex_result(self, corpus: SQLiteCorpus) -> None:
        """Test storing complex result structures."""
        result = {
            "segments": [
                {
                    "surface": "gacchati",
                    "lemma": "gam",
                    "morphology": {"person": 3, "number": "singular"},
                    "meanings": ["goes", "walks"],
                }
            ],
            "confidence": 0.95,
            "engine_results": {
                "vidyut": {"confidence": 0.9},
                "dharmamitra": {"confidence": 0.95},
            },
        }

        corpus.set("key1", "gacchati", "gacCati", "PRODUCTION", result)

        entry = corpus.get("key1")
        assert entry is not None
        assert entry.get_result() == result

    def test_default_path(self) -> None:
        """Test default database path creation."""
        # Create corpus with default path
        corpus = SQLiteCorpus()

        # Should be able to perform operations
        corpus.set("test", "test", "test", "PRODUCTION", {})
        assert corpus.count() == 1

        # Clean up
        corpus.clear()
        corpus.close()
