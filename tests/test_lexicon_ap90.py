"""Opt-in Apte (AP90, GPL-3.0) source: build script and lexicon wiring."""

from __future__ import annotations

import importlib.util
import sqlite3
import zipfile
from pathlib import Path

import pytest

from sanskrit_analyzer import lexicon

ROOT = Path(__file__).resolve().parent.parent
FIXTURE = ROOT / "tests" / "data" / "ap90_mini.xml"

_spec = importlib.util.spec_from_file_location(
    "build_apte_index", ROOT / "scripts" / "build_apte_index.py"
)
builder = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(builder)


@pytest.fixture
def clean_env(tmp_path, monkeypatch):
    """No real ap90 file can leak in: HOME is empty and the env var unset."""
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.delenv("SANSKRIT_AP90_DB", raising=False)
    return tmp_path


def _make_zip(tmp_path):
    z = tmp_path / "ap90xml.zip"
    with zipfile.ZipFile(z, "w") as zf:
        zf.write(FIXTURE, "xml/ap90.xml")
    return z


@pytest.mark.parametrize("kind", ["xml", "zip"])
def test_build_from_xml_and_zip(clean_env, kind):
    src = FIXTURE if kind == "xml" else _make_zip(clean_env)
    out = clean_env / "ap90.sqlite"
    assert builder.main(["--xml", str(src), "--out", str(out)]) == 0
    con = sqlite3.connect(out)
    assert [r[1] for r in con.execute("PRAGMA table_info(ap90)")] == [
        "key", "key_stem", "lnum", "page", "text", "hom",
    ]
    assert con.execute("SELECT COUNT(*) FROM ap90").fetchone()[0] == 3
    assert con.execute("PRAGMA index_list(ap90)").fetchall()
    con.close()


def test_zip_without_ap90_xml_raises(clean_env):
    bad = clean_env / "bad.zip"
    with zipfile.ZipFile(bad, "w") as zf:
        zf.writestr("other.txt", "x")
    with pytest.raises(ValueError, match="ap90.xml"):
        builder.build(bad, clean_env / "ap90.sqlite")


@pytest.mark.parametrize("where", ["env", "home", "none"])
def test_lookup_prefix_availability(clean_env, monkeypatch, where):
    db = clean_env / "ap90.sqlite"
    builder.build(FIXTURE, db)
    if where == "env":
        monkeypatch.setenv("SANSKRIT_AP90_DB", str(db))
    elif where == "home":
        lex = clean_env / "home" / ".sanskrit_analyzer" / "lexicon"
        lex.mkdir(parents=True)
        db.rename(lex / "ap90.sqlite")
    found = where != "none"
    assert lexicon.is_available("ap90") is found
    entries = lexicon.lookup("rAma", sources=["ap90"])
    assert lexicon.prefix("r", sources=["ap90"]) == (["rAjan", "rAma"] if found else [])
    assert len(entries) == (1 if found else 0)
    if found:
        (e,) = entries
        assert e.source == "ap90" and e.page == "10,1"
        assert e.text == "m. a hand-written sample gloss one"
        assert e.licence == "GPL-3.0" and "Apte" in e.acknowledgement


def test_sources_do_not_cross(clean_env, monkeypatch):
    db = clean_env / "ap90.sqlite"
    builder.build(FIXTURE, db)
    monkeypatch.setenv("SANSKRIT_AP90_DB", str(db))
    monkeypatch.setattr(lexicon, "resolve_mw_db", lambda: None)
    assert lexicon.lookup("rAma", sources=["mw"]) == []
    assert lexicon.prefix("r", sources=["mw"]) == []


def test_ap90_out_of_defaults(clean_env, monkeypatch):
    others = sorted(k for k in lexicon._SOURCES if k != "ap90")
    before = (lexicon.available_sources(), lexicon.is_available())
    assert "ap90" not in before[0]
    db = clean_env / "ap90.sqlite"
    builder.build(FIXTURE, db)
    monkeypatch.setenv("SANSKRIT_AP90_DB", str(db))
    assert "ap90" not in {e.source for e in lexicon.lookup("rAma")}
    assert lexicon.lookup("rAma") == lexicon.lookup("rAma", sources=others)
    assert lexicon.prefix("r") == lexicon.prefix("r", sources=others)
    assert lexicon.is_available() == before[1]


def test_no_in_package_ap90_path(clean_env):
    assert not list((Path(lexicon.__file__).parent).rglob("ap90*"))
