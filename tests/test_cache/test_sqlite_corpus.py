"""Tests for SQLite corpus storage."""

import sqlite3
import threading
from pathlib import Path

import pytest

from sanskrit_analyzer.cache.sqlite_corpus import SQLiteCorpus
from tests._cases import check_cases

P = "PRODUCTION"


@pytest.fixture
def make_corpus(tmp_path: Path):
    """Factory for fresh corpora; each table row gets its own database file."""
    made: list[SQLiteCorpus] = []

    def make(**kwargs) -> SQLiteCorpus:
        corpus = SQLiteCorpus(db_path=str(tmp_path / f"c{len(made)}.db"), **kwargs)
        made.append(corpus)
        return corpus

    yield make
    for corpus in made:
        corpus.close()


def test_init_creates_tables(make_corpus) -> None:
    cursor = make_corpus()._conn.cursor()
    for table in ("analyses", "analyses_fts"):
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table,))
        assert cursor.fetchone() is not None, table


COMPLEX = {
    "segments": [
        {
            "surface": "gacchati",
            "lemma": "gam",
            "morphology": {"person": 3, "number": "singular"},
            "meanings": ["goes", "walks"],
        }
    ],
    "confidence": 0.95,
    "engine_results": {"vidyut": {"confidence": 0.9}, "local_byt5": {"confidence": 0.95}},
}

ROUND_TRIP_CASES = [
    ("simple", "gacchati", "gacCati", P, {"segments": [{"surface": "test"}], "confidence": 0.9}),
    ("devanagari_text_and_result", "गच्छति", "gacCati", P, {"text": "गच्छति"}),
    ("nested_result", "gacchati", "gacCati", "ACADEMIC", COMPLEX),
]


def test_round_trip(make_corpus) -> None:
    def check(original, slp1, mode, result):
        corpus = make_corpus()
        corpus.set("key1", original, slp1, mode, result)
        entry = corpus.get("key1")
        assert entry is not None
        assert (entry.id, entry.original_text, entry.normalized_slp1, entry.mode) == (
            "key1", original, slp1, mode,
        )
        assert entry.get_result() == result

    check_cases(ROUND_TRIP_CASES, check)


def _get_missing(c):
    assert c.get("nonexistent") is None


def _get_bumps_access_count(c):
    c.set("key1", "test", "test", P, {})
    first = c.get("key1").access_count
    assert c.get("key1").access_count == first + 1


def _count_tracks_sets(c):
    assert c.count() == 0
    c.set("key1", "test1", "test1", P, {})
    assert c.count() == 1
    c.set("key2", "test2", "test2", P, {})
    assert c.count() == 2


def _delete(c):
    c.set("key1", "test", "test", P, {})
    assert c.delete("key1") is True
    assert c.count() == 0
    assert c.get("key1") is None


def _delete_missing(c):
    assert c.delete("nonexistent") is False


def _clear_returns_count(c):
    c.set("key1", "test1", "test1", P, {})
    c.set("key2", "test2", "test2", P, {})
    assert c.clear() == 2
    assert c.count() == 0


def _update_disambiguation(c):
    c.set("key1", "test", "test", P, {})
    assert c.update_disambiguation("key1", 2) is True
    entry = c.get("key1")
    assert (entry.disambiguated, entry.selected_parse) == (True, 2)


def _update_disambiguation_missing(c):
    assert c.update_disambiguation("nonexistent", 0) is False


def _set_upserts(c):
    c.set("key1", "test1", "test1", P, {"version": 1})
    c.set("key1", "test1", "test1", P, {"version": 2})
    assert c.count() == 1
    assert c.get("key1").get_result() == {"version": 2}


def _set_keeps_disambiguation(c):
    # Re-analyzing the same key (e.g. cache refresh) must keep the user's choice.
    c.set("key1", "test", "test", P, {"version": 1})
    c.update_disambiguation("key1", 3)
    c.set("key1", "test", "test", P, {"version": 2})
    entry = c.get("key1")
    assert entry.get_result() == {"version": 2}
    assert (entry.disambiguated, entry.selected_parse) == (True, 3)


def _set_keeps_created_at(c):
    c.set("key1", "test", "test", P, {"version": 1})
    first = c.get("key1")
    c.set("key1", "test", "test", P, {"version": 2})
    assert c.get("key1").created_at == first.created_at


def _stats(c):
    c.set("key1", "test1", "test1", P, {})
    c.set("key2", "test2", "test2", P, {})
    c.update_disambiguation("key1", 0)
    c.get("key1")
    c.get("key2")
    stats = c.stats()
    assert stats.total_entries == 2
    assert stats.disambiguated_entries == 1
    assert stats.total_accesses >= 4  # 2 sets + 2 gets


def _search_fts(c):
    c.set("key1", "gacchati nayati", "gacCati nayati", P, {})
    c.set("key2", "pazyati vadati", "pazyati vadati", P, {})
    c.set("key3", "gacchati vadati", "gacCati vadati", P, {})
    assert sorted(r.id for r in c.search("gacchati")) == ["key1", "key3"]


def _get_by_mode(c):
    c.set("key1", "test1", "test1", P, {})
    c.set("key2", "test2", "test2", "ACADEMIC", {})
    c.set("key3", "test3", "test3", P, {})
    assert len(c.get_by_mode(P)) == 2
    assert len(c.get_by_mode("ACADEMIC")) == 1


def _get_recent_honours_limit(c):
    for i in (1, 2, 3):
        c.set(f"key{i}", f"test{i}", f"test{i}", P, {})
    # Same-second timestamps, so order is not pinned; only the limit is.
    ids = {r.id for r in c.get_recent(limit=2)}
    assert len(ids) == 2
    assert ids <= {"key1", "key2", "key3"}


# (id, scenario on a fresh default corpus)
CORPUS_CASES = [
    ("get_missing_is_none", _get_missing),
    ("get_bumps_access_count", _get_bumps_access_count),
    ("count_tracks_sets", _count_tracks_sets),
    ("delete_existing", _delete),
    ("delete_missing_false", _delete_missing),
    ("clear_returns_rows_removed", _clear_returns_count),
    ("update_disambiguation", _update_disambiguation),
    ("update_disambiguation_missing_false", _update_disambiguation_missing),
    ("set_upserts_one_row", _set_upserts),
    ("repeat_set_keeps_disambiguation", _set_keeps_disambiguation),
    ("repeat_set_keeps_created_at", _set_keeps_created_at),
    ("stats_totals", _stats),
    ("search_is_full_text", _search_fts),
    ("get_by_mode_filters", _get_by_mode),
    ("get_recent_honours_limit", _get_recent_honours_limit),
]


def test_corpus_operations(make_corpus) -> None:
    check_cases(CORPUS_CASES, lambda scenario: scenario(make_corpus()))


def test_max_rows_prune(make_corpus) -> None:
    """set() evicts least-recently-accessed rows above max_rows."""
    corpus = make_corpus(max_rows=3)
    for i in range(3):
        corpus.set(f"key{i}", f"t{i}", f"t{i}", P, {})
    assert corpus.count() == 3

    # Touch key1/key2 so key0 is the least-recently-accessed.
    corpus.get("key1")
    corpus.get("key2")

    corpus.set("key3", "t3", "t3", P, {})
    assert corpus.count() == 3
    assert corpus.get("key0") is None
    assert corpus.get("key3") is not None

    # max_rows=None disables pruning entirely.
    unbounded = make_corpus(max_rows=None)
    for i in range(10):
        unbounded.set(f"key{i}", f"t{i}", f"t{i}", P, {})
    assert unbounded.count() == 10


def test_close_closes_all_thread_connections(make_corpus) -> None:
    """close() releases connections opened on other threads too."""
    corpus = make_corpus()
    corpus.set("key1", "t", "t", P, {})  # opens main-thread conn

    opened: list = []

    def worker() -> None:
        corpus.set("key2", "t", "t", P, {})  # opens worker conn
        opened.append(corpus._conn)

    t = threading.Thread(target=worker)
    t.start()
    t.join()

    assert len(corpus._connections) == 2
    corpus.close()
    assert corpus._connections == []
    # The worker's connection is closed even though close() ran on main thread.
    with pytest.raises(sqlite3.ProgrammingError):
        opened[0].execute("SELECT 1")


def test_default_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """No db_path means ~/.sanskrit_analyzer/corpus.db.

    HOME is redirected so the test never clears the developer's real corpus.
    """
    monkeypatch.setenv("HOME", str(tmp_path))
    corpus = SQLiteCorpus()
    try:
        corpus.set("test", "test", "test", P, {})
        assert corpus.count() == 1
        assert (tmp_path / ".sanskrit_analyzer" / "corpus.db").exists()
    finally:
        corpus.close()
