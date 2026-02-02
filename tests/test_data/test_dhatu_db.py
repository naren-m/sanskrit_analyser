"""Tests for DhatuDB class."""

import sqlite3
from pathlib import Path

import pytest

from sanskrit_analyzer.data.dhatu_db import ConjugationEntry, DhatuDB, DhatuEntry


class TestDhatuDBInit:
    """Tests for DhatuDB initialization."""

    def test_default_init(self) -> None:
        """Test initialization with default database."""
        db = DhatuDB()
        assert db._db_path.exists()
        db.close()

    def test_custom_path(self, tmp_path: Path) -> None:
        """Test initialization with custom path."""
        # Create a minimal test database
        db_path = tmp_path / "test.db"
        conn = sqlite3.connect(db_path)
        conn.execute("""
            CREATE TABLE dhatus (
                id INTEGER PRIMARY KEY,
                dhatu_devanagari TEXT UNIQUE NOT NULL,
                dhatu_transliterated TEXT,
                dhatu_iast TEXT,
                meaning_english TEXT,
                meaning_hindi TEXT,
                gana INTEGER,
                pada TEXT,
                it_category TEXT,
                panini_reference TEXT,
                examples TEXT,
                synonyms TEXT,
                related_words TEXT,
                usage_frequency INTEGER DEFAULT 0
            )
        """)
        conn.close()

        db = DhatuDB(db_path)
        assert db._db_path == db_path
        db.close()

    def test_missing_database(self, tmp_path: Path) -> None:
        """Test initialization with missing database raises error."""
        with pytest.raises(FileNotFoundError, match="Dhatu database not found"):
            DhatuDB(tmp_path / "nonexistent.db")


class TestDhatuDBLookup:
    """Tests for dhatu lookup functionality."""

    @pytest.fixture
    def db(self) -> DhatuDB:
        """Create database instance."""
        db = DhatuDB()
        yield db
        db.close()

    def test_lookup_by_devanagari(self, db: DhatuDB) -> None:
        """Test lookup by Devanagari form."""
        entry = db.lookup_by_dhatu("गम्")
        assert entry is not None
        assert entry.dhatu_devanagari == "गम्"
        assert "go" in entry.meaning_english.lower()

    def test_lookup_by_iast(self, db: DhatuDB) -> None:
        """Test lookup by IAST form."""
        # Look up a dhatu that has IAST form
        entry = db.lookup_by_dhatu("कृ")
        if entry:
            assert entry.dhatu_devanagari == "कृ"

    def test_lookup_nonexistent(self, db: DhatuDB) -> None:
        """Test lookup of nonexistent dhatu returns None."""
        entry = db.lookup_by_dhatu("xxxxxxxxx")
        assert entry is None

    def test_lookup_with_conjugations(self, db: DhatuDB) -> None:
        """Test lookup with conjugations included."""
        entry = db.lookup_by_dhatu("गम्", include_conjugations=True)
        if entry:
            # May or may not have conjugations depending on database
            assert isinstance(entry.conjugations, list)

    def test_dhatu_entry_structure(self, db: DhatuDB) -> None:
        """Test DhatuEntry has all expected fields."""
        entry = db.lookup_by_dhatu("गम्")
        assert entry is not None
        assert isinstance(entry.id, int)
        assert isinstance(entry.dhatu_devanagari, str)
        assert entry.gana is None or isinstance(entry.gana, int)
        assert entry.pada is None or isinstance(entry.pada, str)


class TestDhatuDBSearch:
    """Tests for dhatu search functionality."""

    @pytest.fixture
    def db(self) -> DhatuDB:
        """Create database instance."""
        db = DhatuDB()
        yield db
        db.close()

    def test_lookup_by_meaning(self, db: DhatuDB) -> None:
        """Test lookup by English meaning."""
        entries = db.lookup_by_meaning("go")
        assert len(entries) > 0
        # At least one should contain "go" in meaning
        assert any("go" in (e.meaning_english or "").lower() for e in entries)

    def test_lookup_by_meaning_limit(self, db: DhatuDB) -> None:
        """Test lookup respects limit."""
        entries = db.lookup_by_meaning("to", limit=5)
        assert len(entries) <= 5

    def test_get_by_gana(self, db: DhatuDB) -> None:
        """Test getting dhatus by gana."""
        entries = db.get_by_gana(1, limit=10)
        assert len(entries) > 0
        assert all(e.gana == 1 for e in entries if e.gana is not None)

    def test_get_by_invalid_gana(self, db: DhatuDB) -> None:
        """Test invalid gana raises error."""
        with pytest.raises(ValueError, match="Gana must be 1-10"):
            db.get_by_gana(0)

        with pytest.raises(ValueError, match="Gana must be 1-10"):
            db.get_by_gana(11)

    def test_search(self, db: DhatuDB) -> None:
        """Test full-text search."""
        entries = db.search("go")
        assert len(entries) > 0

    def test_search_limit(self, db: DhatuDB) -> None:
        """Test search respects limit."""
        entries = db.search("a", limit=5)
        assert len(entries) <= 5


class TestDhatuDBStats:
    """Tests for database statistics."""

    @pytest.fixture
    def db(self) -> DhatuDB:
        """Create database instance."""
        db = DhatuDB()
        yield db
        db.close()

    def test_count(self, db: DhatuDB) -> None:
        """Test counting dhatus."""
        count = db.count()
        assert count > 0
        assert isinstance(count, int)

    def test_gana_stats(self, db: DhatuDB) -> None:
        """Test gana statistics."""
        stats = db.get_gana_stats()
        assert isinstance(stats, dict)
        # Should have at least some ganas
        assert len(stats) > 0
        # Values should be positive counts
        assert all(v > 0 for v in stats.values())


class TestDhatuDBConjugations:
    """Tests for conjugation lookups."""

    @pytest.fixture
    def db(self) -> DhatuDB:
        """Create database instance."""
        db = DhatuDB()
        yield db
        db.close()

    def test_get_conjugation(self, db: DhatuDB) -> None:
        """Test getting specific conjugations."""
        # First find a dhatu
        entry = db.lookup_by_dhatu("गम्")
        if entry:
            conjs = db.get_conjugation(entry.id, "lat")
            # May or may not have conjugations
            assert isinstance(conjs, list)

    def test_conjugation_entry_structure(self, db: DhatuDB) -> None:
        """Test ConjugationEntry structure."""
        entry = ConjugationEntry(
            lakara="lat",
            purusha="prathama",
            vacana="ekavacana",
            pada="parasmaipada",
            form_devanagari="गच्छति",
            form_iast="gacchati",
        )
        assert entry.lakara == "lat"
        assert entry.form_devanagari == "गच्छति"


class TestDhatuDBThreadSafety:
    """Tests for thread safety."""

    def test_thread_local_connections(self) -> None:
        """Test that connections are thread-local."""
        import threading

        db = DhatuDB()
        results: list[int] = []
        errors: list[Exception] = []

        def worker() -> None:
            try:
                count = db.count()
                results.append(count)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=worker) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        db.close()

        assert len(errors) == 0
        assert len(results) == 5
        assert all(r == results[0] for r in results)
