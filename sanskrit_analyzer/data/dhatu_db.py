"""Dhatu database access layer.

Provides lookup functionality for Sanskrit verbal roots (dhatus) from the
comprehensive dhatu database.
"""

import sqlite3
import threading
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class ConjugationEntry:
    """A single verb conjugation form."""

    lakara: str  # Tense/mood (lat, lit, lut, etc.)
    purusha: str  # Person (prathama, madhyama, uttama)
    vacana: str  # Number (ekavacana, dvivacana, bahuvacana)
    pada: str  # Voice (parasmaipada, atmanepada)
    form_devanagari: str
    form_iast: str | None = None


@dataclass
class DhatuEntry:
    """Complete information about a dhatu (verbal root)."""

    id: int
    dhatu_devanagari: str
    dhatu_iast: str | None
    meaning_english: str | None
    meaning_hindi: str | None
    gana: int | None  # 1-10 verb class
    pada: str | None  # parasmaipada, atmanepada, ubhayapada
    it_category: str | None
    panini_reference: str | None
    examples: str | None
    synonyms: str | None
    related_words: str | None
    conjugations: list[ConjugationEntry] = field(default_factory=list)


class DhatuDB:
    """Database interface for dhatu lookups.

    Thread-safe SQLite connection management with connection pooling per thread.

    Example:
        db = DhatuDB()
        entry = db.lookup_by_dhatu("गम्")
        if entry:
            print(f"{entry.dhatu_devanagari}: {entry.meaning_english}")
    """

    # Default database path relative to this module
    DEFAULT_DB_PATH = Path(__file__).parent / "comprehensive_dhatu_database.db"

    def __init__(self, db_path: Path | None = None) -> None:
        """Initialize the dhatu database.

        Args:
            db_path: Path to the SQLite database. Defaults to bundled database.
        """
        self._db_path = db_path or self.DEFAULT_DB_PATH
        self._local = threading.local()

        if not self._db_path.exists():
            raise FileNotFoundError(f"Dhatu database not found: {self._db_path}")

    def _get_connection(self) -> sqlite3.Connection:
        """Get thread-local database connection."""
        if not hasattr(self._local, "conn") or self._local.conn is None:
            self._local.conn = sqlite3.connect(
                self._db_path,
                check_same_thread=False,
            )
            self._local.conn.row_factory = sqlite3.Row
        conn: sqlite3.Connection = self._local.conn
        return conn

    def close(self) -> None:
        """Close the database connection for the current thread."""
        if hasattr(self._local, "conn") and self._local.conn is not None:
            self._local.conn.close()
            self._local.conn = None

    def lookup_by_dhatu(
        self,
        dhatu: str,
        include_conjugations: bool = False,
    ) -> DhatuEntry | None:
        """Look up a dhatu by its Devanagari or IAST form.

        Args:
            dhatu: The dhatu in Devanagari or IAST/transliterated form.
            include_conjugations: Whether to include conjugation forms.

        Returns:
            DhatuEntry if found, None otherwise.
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        # Try exact match first (Devanagari, then IAST, then transliterated)
        cursor.execute(
            """
            SELECT * FROM dhatus
            WHERE dhatu_devanagari = ?
               OR dhatu_iast = ?
               OR dhatu_transliterated = ?
            LIMIT 1
            """,
            (dhatu, dhatu, dhatu),
        )

        row = cursor.fetchone()
        if row is None:
            return None

        entry = self._row_to_entry(row)

        if include_conjugations:
            entry.conjugations = self._get_conjugations(entry.id)

        return entry

    def lookup_by_meaning(
        self,
        meaning: str,
        limit: int = 10,
    ) -> list[DhatuEntry]:
        """Look up dhatus by English meaning (partial match).

        Args:
            meaning: English meaning to search for.
            limit: Maximum number of results.

        Returns:
            List of matching DhatuEntry objects.
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT * FROM dhatus
            WHERE meaning_english LIKE ?
            ORDER BY usage_frequency DESC
            LIMIT ?
            """,
            (f"%{meaning}%", limit),
        )

        return [self._row_to_entry(row) for row in cursor.fetchall()]

    def get_by_gana(
        self,
        gana: int,
        limit: int = 100,
    ) -> list[DhatuEntry]:
        """Get all dhatus of a specific gana (verb class).

        Args:
            gana: Gana number (1-10).
            limit: Maximum number of results.

        Returns:
            List of DhatuEntry objects in that gana.
        """
        if not 1 <= gana <= 10:
            raise ValueError(f"Gana must be 1-10, got {gana}")

        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT * FROM dhatus
            WHERE gana = ?
            ORDER BY usage_frequency DESC
            LIMIT ?
            """,
            (gana, limit),
        )

        return [self._row_to_entry(row) for row in cursor.fetchall()]

    def get_conjugation(
        self,
        dhatu_id: int,
        lakara: str,
        purusha: str | None = None,
        vacana: str | None = None,
    ) -> list[ConjugationEntry]:
        """Get specific conjugation forms for a dhatu.

        Args:
            dhatu_id: The dhatu's database ID.
            lakara: Tense/mood (lat, lit, lut, lrt, lot, lan, lin_vidhi, lin_ashir, lun, lrn).
            purusha: Optional person filter.
            vacana: Optional number filter.

        Returns:
            List of matching conjugation entries.
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        query = "SELECT * FROM dhatu_conjugations WHERE dhatu_id = ? AND lakara = ?"
        params: list = [dhatu_id, lakara]

        if purusha:
            query += " AND purusha = ?"
            params.append(purusha)

        if vacana:
            query += " AND vacana = ?"
            params.append(vacana)

        cursor.execute(query, params)

        return [
            ConjugationEntry(
                lakara=row["lakara"],
                purusha=row["purusha"],
                vacana=row["vacana"],
                pada=row["pada"],
                form_devanagari=row["form_devanagari"],
                form_iast=row["form_iast"],
            )
            for row in cursor.fetchall()
        ]

    def search(
        self,
        query: str,
        limit: int = 20,
    ) -> list[DhatuEntry]:
        """Full-text search across dhatu fields.

        Args:
            query: Search query (matches dhatu, meaning, examples).
            limit: Maximum results.

        Returns:
            List of matching DhatuEntry objects.
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        search_pattern = f"%{query}%"
        cursor.execute(
            """
            SELECT * FROM dhatus
            WHERE dhatu_devanagari LIKE ?
               OR dhatu_iast LIKE ?
               OR dhatu_transliterated LIKE ?
               OR meaning_english LIKE ?
               OR meaning_hindi LIKE ?
               OR examples LIKE ?
            ORDER BY usage_frequency DESC
            LIMIT ?
            """,
            (
                search_pattern,
                search_pattern,
                search_pattern,
                search_pattern,
                search_pattern,
                search_pattern,
                limit,
            ),
        )

        return [self._row_to_entry(row) for row in cursor.fetchall()]

    def count(self) -> int:
        """Get total number of dhatus in the database."""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM dhatus")
        result: int = cursor.fetchone()[0]
        return result

    def get_gana_stats(self) -> dict[int, int]:
        """Get count of dhatus per gana.

        Returns:
            Dict mapping gana number to count of dhatus.
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT gana, COUNT(*) as count
            FROM dhatus
            WHERE gana IS NOT NULL
            GROUP BY gana
            ORDER BY gana
            """
        )
        return {row["gana"]: row["count"] for row in cursor.fetchall()}

    def _row_to_entry(self, row: sqlite3.Row) -> DhatuEntry:
        """Convert a database row to a DhatuEntry."""
        return DhatuEntry(
            id=row["id"],
            dhatu_devanagari=row["dhatu_devanagari"],
            dhatu_iast=row["dhatu_iast"],
            meaning_english=row["meaning_english"],
            meaning_hindi=row["meaning_hindi"],
            gana=row["gana"],
            pada=row["pada"],
            it_category=row["it_category"],
            panini_reference=row["panini_reference"],
            examples=row["examples"],
            synonyms=row["synonyms"],
            related_words=row["related_words"],
        )

    def _get_conjugations(self, dhatu_id: int) -> list[ConjugationEntry]:
        """Get all conjugations for a dhatu."""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM dhatu_conjugations WHERE dhatu_id = ?",
            (dhatu_id,),
        )
        return [
            ConjugationEntry(
                lakara=row["lakara"],
                purusha=row["purusha"],
                vacana=row["vacana"],
                pada=row["pada"],
                form_devanagari=row["form_devanagari"],
                form_iast=row["form_iast"],
            )
            for row in cursor.fetchall()
        ]
