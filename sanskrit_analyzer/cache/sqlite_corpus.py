"""SQLite-based corpus storage for persistent analysis caching."""

import json
import sqlite3
import threading
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Optional


@dataclass
class CorpusEntry:
    """An entry in the corpus database."""

    id: str
    original_text: str
    normalized_slp1: str
    mode: str
    result_json: str
    created_at: datetime
    accessed_at: datetime
    access_count: int
    disambiguated: bool
    selected_parse: Optional[int]

    def get_result(self) -> dict[str, Any]:
        """Parse and return the result as a dictionary."""
        result: dict[str, Any] = json.loads(self.result_json)
        return result


@dataclass
class CorpusStats:
    """Statistics for the corpus."""

    total_entries: int = 0
    disambiguated_entries: int = 0
    total_accesses: int = 0


class SQLiteCorpus:
    """SQLite-based persistent storage for analysis results.

    Provides a searchable corpus of analyzed Sanskrit texts with:
    - Full-text search via FTS5
    - Access tracking for corpus analytics
    - Disambiguation state tracking
    - Thread-safe operations

    Example:
        corpus = SQLiteCorpus("sanskrit_corpus.db")
        corpus.set("key123", "gacchati", "gacCati", "PRODUCTION", result_dict)
        entry = corpus.get("key123")
    """

    def __init__(self, db_path: Optional[str] = None) -> None:
        """Initialize the SQLite corpus.

        Args:
            db_path: Path to SQLite database file. Defaults to ~/.sanskrit_analyzer/corpus.db
        """
        if db_path is None:
            config_dir = Path.home() / ".sanskrit_analyzer"
            config_dir.mkdir(parents=True, exist_ok=True)
            db_path = str(config_dir / "corpus.db")

        self._db_path = db_path
        self._local = threading.local()
        self._init_db()

    @property
    def _conn(self) -> sqlite3.Connection:
        """Get thread-local database connection."""
        if not hasattr(self._local, "conn"):
            self._local.conn = sqlite3.connect(self._db_path)
            self._local.conn.row_factory = sqlite3.Row
        conn: sqlite3.Connection = self._local.conn
        return conn

    def _init_db(self) -> None:
        """Initialize database schema."""
        conn = self._conn
        cursor = conn.cursor()

        # Main analyses table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS analyses (
                id TEXT PRIMARY KEY,
                original_text TEXT NOT NULL,
                normalized_slp1 TEXT NOT NULL,
                mode TEXT NOT NULL,
                result_json TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                accessed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                access_count INTEGER DEFAULT 1,
                disambiguated BOOLEAN DEFAULT 0,
                selected_parse INTEGER
            )
        """)

        # Create indexes for common queries
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_normalized_slp1
            ON analyses(normalized_slp1)
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_mode
            ON analyses(mode)
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_accessed_at
            ON analyses(accessed_at)
        """)

        # FTS5 virtual table for full-text search
        cursor.execute("""
            CREATE VIRTUAL TABLE IF NOT EXISTS analyses_fts USING fts5(
                original_text,
                normalized_slp1,
                content='analyses',
                content_rowid='rowid'
            )
        """)

        # Triggers to keep FTS in sync
        cursor.execute("""
            CREATE TRIGGER IF NOT EXISTS analyses_ai AFTER INSERT ON analyses BEGIN
                INSERT INTO analyses_fts(rowid, original_text, normalized_slp1)
                VALUES (new.rowid, new.original_text, new.normalized_slp1);
            END
        """)

        cursor.execute("""
            CREATE TRIGGER IF NOT EXISTS analyses_ad AFTER DELETE ON analyses BEGIN
                INSERT INTO analyses_fts(analyses_fts, rowid, original_text, normalized_slp1)
                VALUES ('delete', old.rowid, old.original_text, old.normalized_slp1);
            END
        """)

        cursor.execute("""
            CREATE TRIGGER IF NOT EXISTS analyses_au AFTER UPDATE ON analyses BEGIN
                INSERT INTO analyses_fts(analyses_fts, rowid, original_text, normalized_slp1)
                VALUES ('delete', old.rowid, old.original_text, old.normalized_slp1);
                INSERT INTO analyses_fts(rowid, original_text, normalized_slp1)
                VALUES (new.rowid, new.original_text, new.normalized_slp1);
            END
        """)

        conn.commit()

    def get(self, key: str) -> Optional[CorpusEntry]:
        """Get an entry by its key.

        Updates accessed_at and access_count.

        Args:
            key: The entry key (typically a hash).

        Returns:
            CorpusEntry if found, None otherwise.
        """
        conn = self._conn
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT id, original_text, normalized_slp1, mode, result_json,
                   created_at, accessed_at, access_count, disambiguated, selected_parse
            FROM analyses WHERE id = ?
            """,
            (key,),
        )

        row = cursor.fetchone()
        if row is None:
            return None

        # Update access tracking
        cursor.execute(
            """
            UPDATE analyses
            SET accessed_at = CURRENT_TIMESTAMP, access_count = access_count + 1
            WHERE id = ?
            """,
            (key,),
        )
        conn.commit()

        return CorpusEntry(
            id=row["id"],
            original_text=row["original_text"],
            normalized_slp1=row["normalized_slp1"],
            mode=row["mode"],
            result_json=row["result_json"],
            created_at=datetime.fromisoformat(row["created_at"]),
            accessed_at=datetime.fromisoformat(row["accessed_at"]),
            access_count=row["access_count"],
            disambiguated=bool(row["disambiguated"]),
            selected_parse=row["selected_parse"],
        )

    def set(
        self,
        key: str,
        original_text: str,
        normalized_slp1: str,
        mode: str,
        result: dict[str, Any],
    ) -> None:
        """Store an analysis result.

        Args:
            key: The entry key (typically a hash).
            original_text: Original input text.
            normalized_slp1: Normalized SLP1 text.
            mode: Analysis mode.
            result: Analysis result dictionary.
        """
        conn = self._conn
        cursor = conn.cursor()

        result_json = json.dumps(result, ensure_ascii=False)

        cursor.execute(
            """
            INSERT OR REPLACE INTO analyses
            (id, original_text, normalized_slp1, mode, result_json, created_at, accessed_at, access_count)
            VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, 1)
            """,
            (key, original_text, normalized_slp1, mode, result_json),
        )
        conn.commit()

    def update_disambiguation(self, key: str, selected_parse: int) -> bool:
        """Update the disambiguation choice for an entry.

        Args:
            key: The entry key.
            selected_parse: Index of the selected parse.

        Returns:
            True if entry was updated, False if not found.
        """
        conn = self._conn
        cursor = conn.cursor()

        cursor.execute(
            """
            UPDATE analyses
            SET disambiguated = 1, selected_parse = ?
            WHERE id = ?
            """,
            (selected_parse, key),
        )
        conn.commit()

        return cursor.rowcount > 0

    def delete(self, key: str) -> bool:
        """Delete an entry.

        Args:
            key: The entry key.

        Returns:
            True if entry was deleted, False if not found.
        """
        conn = self._conn
        cursor = conn.cursor()

        cursor.execute("DELETE FROM analyses WHERE id = ?", (key,))
        conn.commit()

        return cursor.rowcount > 0

    def count(self) -> int:
        """Get the total number of entries.

        Returns:
            Number of entries in the corpus.
        """
        cursor = self._conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM analyses")
        result = cursor.fetchone()
        return int(result[0]) if result else 0

    def stats(self) -> CorpusStats:
        """Get corpus statistics.

        Returns:
            CorpusStats with aggregated metrics.
        """
        cursor = self._conn.cursor()

        cursor.execute("SELECT COUNT(*) FROM analyses")
        total = cursor.fetchone()
        total_entries = int(total[0]) if total else 0

        cursor.execute("SELECT COUNT(*) FROM analyses WHERE disambiguated = 1")
        disambiguated = cursor.fetchone()
        disambiguated_entries = int(disambiguated[0]) if disambiguated else 0

        cursor.execute("SELECT SUM(access_count) FROM analyses")
        accesses = cursor.fetchone()
        total_accesses = int(accesses[0]) if accesses and accesses[0] else 0

        return CorpusStats(
            total_entries=total_entries,
            disambiguated_entries=disambiguated_entries,
            total_accesses=total_accesses,
        )

    def search(self, query: str, limit: int = 10) -> list[CorpusEntry]:
        """Full-text search in the corpus.

        Args:
            query: Search query string.
            limit: Maximum results to return.

        Returns:
            List of matching CorpusEntry objects.
        """
        cursor = self._conn.cursor()

        # Use FTS5 for search
        cursor.execute(
            """
            SELECT a.id, a.original_text, a.normalized_slp1, a.mode, a.result_json,
                   a.created_at, a.accessed_at, a.access_count, a.disambiguated, a.selected_parse
            FROM analyses a
            INNER JOIN analyses_fts f ON a.rowid = f.rowid
            WHERE analyses_fts MATCH ?
            LIMIT ?
            """,
            (query, limit),
        )

        results: list[CorpusEntry] = []
        for row in cursor.fetchall():
            results.append(
                CorpusEntry(
                    id=row["id"],
                    original_text=row["original_text"],
                    normalized_slp1=row["normalized_slp1"],
                    mode=row["mode"],
                    result_json=row["result_json"],
                    created_at=datetime.fromisoformat(row["created_at"]),
                    accessed_at=datetime.fromisoformat(row["accessed_at"]),
                    access_count=row["access_count"],
                    disambiguated=bool(row["disambiguated"]),
                    selected_parse=row["selected_parse"],
                )
            )

        return results

    def get_by_mode(self, mode: str, limit: int = 100) -> list[CorpusEntry]:
        """Get entries by analysis mode.

        Args:
            mode: Analysis mode to filter by.
            limit: Maximum results to return.

        Returns:
            List of matching CorpusEntry objects.
        """
        cursor = self._conn.cursor()

        cursor.execute(
            """
            SELECT id, original_text, normalized_slp1, mode, result_json,
                   created_at, accessed_at, access_count, disambiguated, selected_parse
            FROM analyses
            WHERE mode = ?
            ORDER BY accessed_at DESC
            LIMIT ?
            """,
            (mode, limit),
        )

        results: list[CorpusEntry] = []
        for row in cursor.fetchall():
            results.append(
                CorpusEntry(
                    id=row["id"],
                    original_text=row["original_text"],
                    normalized_slp1=row["normalized_slp1"],
                    mode=row["mode"],
                    result_json=row["result_json"],
                    created_at=datetime.fromisoformat(row["created_at"]),
                    accessed_at=datetime.fromisoformat(row["accessed_at"]),
                    access_count=row["access_count"],
                    disambiguated=bool(row["disambiguated"]),
                    selected_parse=row["selected_parse"],
                )
            )

        return results

    def get_recent(self, limit: int = 10) -> list[CorpusEntry]:
        """Get most recently accessed entries.

        Args:
            limit: Maximum results to return.

        Returns:
            List of CorpusEntry objects ordered by access time.
        """
        cursor = self._conn.cursor()

        cursor.execute(
            """
            SELECT id, original_text, normalized_slp1, mode, result_json,
                   created_at, accessed_at, access_count, disambiguated, selected_parse
            FROM analyses
            ORDER BY accessed_at DESC
            LIMIT ?
            """,
            (limit,),
        )

        results: list[CorpusEntry] = []
        for row in cursor.fetchall():
            results.append(
                CorpusEntry(
                    id=row["id"],
                    original_text=row["original_text"],
                    normalized_slp1=row["normalized_slp1"],
                    mode=row["mode"],
                    result_json=row["result_json"],
                    created_at=datetime.fromisoformat(row["created_at"]),
                    accessed_at=datetime.fromisoformat(row["accessed_at"]),
                    access_count=row["access_count"],
                    disambiguated=bool(row["disambiguated"]),
                    selected_parse=row["selected_parse"],
                )
            )

        return results

    def clear(self) -> int:
        """Clear all entries from the corpus.

        Returns:
            Number of entries deleted.
        """
        conn = self._conn
        cursor = conn.cursor()

        cursor.execute("SELECT COUNT(*) FROM analyses")
        count_result = cursor.fetchone()
        count = int(count_result[0]) if count_result else 0

        cursor.execute("DELETE FROM analyses")
        conn.commit()

        return count

    def close(self) -> None:
        """Close the database connection."""
        if hasattr(self._local, "conn"):
            self._local.conn.close()
            del self._local.conn
