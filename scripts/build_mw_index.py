#!/usr/bin/env python3
"""Build the Monier-Williams SQLite index used by ``sanskrit_analyzer.lexicon``.

Usage: ``build_mw_index.py <mwxml.zip | mw.xml> <out.sqlite>``

Takes a local copy of the CDSL ``mwxml.zip`` (or the extracted ``mw.xml``) and
never downloads anything. Writes table ``mw(key, key_stem, lnum, page, text,
hom)`` with an index on ``key``. ``key`` is the SLP1 headword (``key1``),
``key_stem`` is ``key2`` with markup and accents removed.

The body cleaning (tag regexes, accent strip, CDSL id scrub) is written to match
the yoga_sutras ``DictionaryService`` approach. That repo was not available when
this was written, so these are equivalent regexes, not a verbatim copy.
"""
from __future__ import annotations

import html
import re
import sqlite3
import sys
import zipfile
from pathlib import Path

_ENTRY = re.compile(r"<(H\d+[A-Za-z]*)>(.*?)</\1>", re.S)
_TAG = re.compile(r"<[^>]+>")
_WS = re.compile(r"\s+")
# CDSL bookkeeping that is not gloss text: <info .../>, <L>, <pc>, <lbinfo .../>.
_CDSL_ID = re.compile(r"<(?:info|lbinfo)\b[^>]*/?>|<L>.*?</L>|<pc>.*?</pc>", re.S)
# Inline emphasis / transliteration wrappers: {%italic%}, {#slp1#}, {@bold@}.
_MARKS = re.compile(r"\{[%#@]|[%#@]\}")
# Vedic accent marks in SLP1, only meaningful inside <s>...</s>.
_S_SPAN = re.compile(r"(<s>)(.*?)(</s>)", re.S)
_ACCENTS = re.compile(r"[/\\^]")


def clean_body(raw: str) -> str:
    """Plain-text gloss from a raw MW ``<body>`` fragment."""
    raw = _CDSL_ID.sub(" ", raw)
    raw = _S_SPAN.sub(lambda m: m.group(1) + _ACCENTS.sub("", m.group(2)) + m.group(3), raw)
    raw = _MARKS.sub("", raw)
    text = html.unescape(_TAG.sub(" ", raw))
    return _WS.sub(" ", text).replace("¦", "").strip()


def _field(tag: str, chunk: str) -> str:
    m = re.search(rf"<{tag}>(.*?)</{tag}>", chunk, re.S)
    return m.group(1).strip() if m else ""


def parse_entries(xml: str):
    """Yield ``(key, key_stem, lnum, page, text, hom)`` per MW entry."""
    for m in _ENTRY.finditer(xml):
        chunk = m.group(2)
        key = _field("key1", chunk)
        body = _field("body", chunk)
        if not key or not body:
            continue
        stem = clean_body(_field("key2", chunk)).replace("-", "") or key
        yield (
            key,
            _ACCENTS.sub("", stem),
            _field("L", chunk),
            _field("pc", chunk),
            clean_body(body),
            _field("hom", chunk),
        )


def read_xml(path: Path) -> str:
    if path.suffix == ".zip":
        with zipfile.ZipFile(path) as zf:
            name = next(n for n in zf.namelist() if n.endswith("mw.xml"))
            return zf.read(name).decode("utf-8")
    return path.read_text(encoding="utf-8")


def build(src: Path, out: Path) -> int:
    """Write the SQLite index to ``out``; returns the number of rows."""
    if out.exists():
        out.unlink()
    con = sqlite3.connect(out)
    try:
        con.execute(
            "CREATE TABLE mw (key TEXT, key_stem TEXT, lnum TEXT, page TEXT, "
            "text TEXT, hom TEXT)"
        )
        con.executemany("INSERT INTO mw VALUES (?,?,?,?,?,?)", parse_entries(read_xml(src)))
        con.execute("CREATE INDEX mw_key ON mw (key)")
        con.commit()
        return con.execute("SELECT COUNT(*) FROM mw").fetchone()[0]
    finally:
        con.close()


def main(argv: list[str]) -> int:
    if len(argv) != 3:
        print(__doc__)
        return 2
    n = build(Path(argv[1]), Path(argv[2]))
    print(f"wrote {n} rows to {argv[2]}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
