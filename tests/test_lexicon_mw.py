"""Monier-Williams source and prefix() in the lexicon, built from a tiny fixture."""

from __future__ import annotations

import importlib.util
import re
import sqlite3
from pathlib import Path

import pytest

from sanskrit_analyzer import lexicon

ROOT = Path(__file__).resolve().parent.parent
FIXTURE = ROOT / "tests" / "fixtures" / "mw_mini.xml"

_spec = importlib.util.spec_from_file_location(
    "build_mw_index", ROOT / "scripts" / "build_mw_index.py"
)
builder = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(builder)


@pytest.fixture
def mw_db(tmp_path, monkeypatch):
    db = tmp_path / "mw.sqlite"
    builder.build(FIXTURE, db)
    monkeypatch.setenv("SANSKRIT_MW_DB", str(db))
    return db


def test_build_index_from_fixture(mw_db):
    con = sqlite3.connect(mw_db)
    cols = [r[1] for r in con.execute("PRAGMA table_info(mw)")]
    assert cols == ["key", "key_stem", "lnum", "page", "text", "hom"]
    assert con.execute("SELECT COUNT(*) FROM mw").fetchone()[0] == 14
    assert con.execute("PRAGMA index_list(mw)").fetchall()
    con.close()


def test_failed_build_keeps_old_index(mw_db, tmp_path):
    import zipfile

    bad = tmp_path / "bad.zip"
    with zipfile.ZipFile(bad, "w") as zf:
        zf.writestr("other.txt", "x")
    with pytest.raises(ValueError, match="mw.xml"):
        builder.build(bad, mw_db)
    con = sqlite3.connect(mw_db)
    assert con.execute("SELECT COUNT(*) FROM mw").fetchone()[0] == 14
    con.close()
    assert not mw_db.with_name(mw_db.name + ".tmp").exists()


# "rāma" is spelt differently in all three encodings.
@pytest.mark.parametrize("word", ["राम", "rāma", "rAma"])
def test_lookup_mw_any_script(mw_db, word):
    entries = lexicon.lookup(word, sources=["mw"])
    assert [e.fields["hom"] for e in entries] == ["1", "2"]
    e = entries[1]
    assert e.source == "mw" and e.key == "rAma" and e.page == "877,3"
    assert e.lnum == "4" and "lnum" not in e.fields
    assert e.fields["key_stem"] == "rAma"
    assert "Rama, son of Dasharatha & hero" in e.text
    assert e.licence == "CC BY-SA 4.0"
    assert "Cologne" in e.acknowledgement


def test_body_cleaning_strips_accents_and_ids(mw_db):
    (e,) = lexicon.lookup("agni", sources=["mw"])
    assert e.text == "m. fire, sacrificial fire RV."  # clean_definition drops the headword echo
    assert e.fields["key_stem"] == "agni"  # key2 "a/gni" loses its accent
    assert "<" not in e.text and "sup" not in e.text
    # cited root loses its glued CDSL id; accented body word loses its accent
    (s,) = lexicon.lookup("saNga", sources=["mw"])
    assert s.text == "m. fr. √ 1. sañj, cf. agni"
    assert "228458" not in s.text and "/" not in s.text


def test_mw_entries_never_carry_promoted_columns_in_fields(mw_db):
    entries = [e for w in ("rAma", "agni", "saNga", "rAjan") for e in lexicon.lookup(w, sources=["mw"])]
    assert entries
    assert all(not (lexicon._PROMOTED & e.fields.keys()) for e in entries)


def test_prefix_sorted_distinct(mw_db):
    # rAma appears twice in the fixture (two homonyms) but once in the result.
    assert lexicon.prefix("रा", sources=["mw"]) == ["rAjan", "rAmAyaRa", "rAma"]  # code-point order: A < a
    assert lexicon.prefix("", sources=["mw"]) == []


def test_prefix_limit(mw_db):
    assert lexicon.prefix("rA", limit=2, sources=["mw"]) == ["rAjan", "rAmAyaRa"]


def test_prefix_unknown_source_raises(mw_db):
    with pytest.raises(KeyError, match="unknown Layer B source"):
        lexicon.prefix("rA", sources=["nosuchdict"])


def test_mw_unavailable_returns_empty(monkeypatch):
    monkeypatch.setattr(lexicon, "resolve_mw_db", lambda: None)
    assert lexicon.is_available("mw") is False
    assert lexicon.lookup("rAma", sources=["mw"]) == []
    assert lexicon.prefix("rA", sources=["mw"]) == []


@pytest.mark.skipif(not lexicon.is_available("skd"), reason="Layer B TSVs not present")
def test_layerb_lookup_unchanged(mw_db):
    entries = lexicon.lookup("rAma", sources=["skd", "vcp"])
    assert entries and {e.source for e in entries} <= {"skd", "vcp"}
    assert all(e.licence is None and e.acknowledgement is None for e in entries)
    assert lexicon.resolve_data_dir() != mw_db.parent
    assert "rAma" in lexicon.prefix("rAm", limit=50, sources=["skd", "vcp"])


@pytest.mark.parametrize(
    "key,start",
    [
        ("kAnta", "mf(ā)n. ( prob. causing rest) dark, black"),
        ("haM~sa", "m. a goose ~ swan"),
        ("ajita", "m. pl. a class of deified beings"),
        ("vAmana", "mf(ā or ī)n. dwarfish"),
        ("dfzadupala", "f(ā). du. the upper and lower millstone"),
    ],
)
def test_multiword_and_attributed_markers(mw_db, key, start):
    (e,) = lexicon.lookup(key, sources=["mw"])
    assert e.text == start


def test_no_accent_debris_in_any_row(mw_db):
    con = sqlite3.connect(mw_db)
    texts = [r[0] for r in con.execute("SELECT text FROM mw")]
    con.close()
    assert texts and not [t for t in texts if re.match(r"^[A-Za-z]/\s*\)", t) or re.search(r"[A-Za-z]/ ", t)]
