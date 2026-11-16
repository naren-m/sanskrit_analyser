#!/usr/bin/env python3
"""Build the Monier-Williams SQLite index used by ``sanskrit_analyzer.lexicon``.

Usage: ``build_mw_index.py <mwxml.zip | mw.xml> <out.sqlite>``

Takes a local copy of the CDSL ``mwxml.zip`` (or the extracted ``mw.xml``) and
never downloads anything. Writes table ``mw(key, key_stem, lnum, page, text,
hom)`` with an index on ``key``. ``key`` is the SLP1 headword (``key1``),
``key_stem`` is ``key2`` with markup and accents removed.

The body cleaning (``_DEF_*`` regexes, accent strip, ``_CDSL_ID`` scrub, and
``clean_definition``) is copied from ``naren-m/yoga_sutras``
``backend/app/services/dictionary_service.py`` (``DictionaryService``), not
imported. Only the XML-to-flat-text step before it is local to this script.
"""
from __future__ import annotations

import html
import os
import re
import sqlite3
import sys
import zipfile
from pathlib import Path

from indic_transliteration import sanscript
from indic_transliteration.sanscript import transliterate

_ENTRY = re.compile(r"<(H\d+[A-Za-z]*)>(.*?)</\1>", re.S)
_TAG = re.compile(r"<[^>]+>")
_WS = re.compile(r"\s+")
# CDSL XML bookkeeping that is not gloss text: <info .../>, <L>, <pc>, <lbinfo .../>.
_XML_BOOKKEEPING = re.compile(r"<(?:info|lbinfo)\b[^>]*/?>|<L>.*?</L>|<pc>.*?</pc>", re.S)
# Inline emphasis / transliteration wrappers: {%italic%}, {#slp1#}, {@bold@}.
_MARKS = re.compile(r"\{[%#@]|[%#@]\}")
# Vedic accent marks in SLP1 headwords (key_stem only; bodies use _DEF_ACCENT).
_ACCENTS = re.compile(r"[/\\^]")

# --- copied from yoga_sutras DictionaryService ---------------------------------
_DEF_WORD = re.compile(r'[A-Za-z/]+')
_DEF_TRAIL_REF = re.compile(r'[\d,\-]{4,}[a-z]?\s*$')
_DEF_DOUBLED = re.compile(r'(\w{4,})\1+')
_DEF_ACCENT = re.compile(r'(?<=[A-Za-z])/(?=[A-Za-z])')
_DEF_BODY_START = re.compile(r'^(?:(?:mfn|mf|m|f|n|ind|cl|p{1,2})\.?$|[0-9(&A-Z])')
# MW states a derived word's origin as 'fr. √ 1. viṣ'; CDSL glues its own entry
# id onto some roots: 'sañj.228458'.
_CITED_ROOT = re.compile(r'√\s*(?:(?:\d+\.?|and)\s*)*([^\s,;)\]]+)')
_CDSL_ID = re.compile(r'\.\d+$')


def clean_definition(value: str) -> str:
    """Make a raw CDSL entry body readable (yoga_sutras ``clean_definition``)."""

    def _xlit_token(m: re.Match) -> str:
        token = m.group(0)
        core = token.replace('/', '')  # '/' marks vedic accent in MW
        if core and core[0].islower() and any(c.isupper() for c in core[1:]):
            try:
                return transliterate(core, sanscript.SLP1, sanscript.IAST)
            except Exception:
                return token
        return token

    text = _DEF_WORD.sub(_xlit_token, value)
    text = _DEF_ACCENT.sub('', text)
    text = _DEF_DOUBLED.sub(r'\1', text)
    text = _DEF_TRAIL_REF.sub('', text)
    stripped = re.sub(r'^(?:\S*[^\x00-\x7F]\S*\s+)+', '', text)
    if len(stripped) >= 3:
        text = stripped
    tokens = text.split(' ')
    for i, token in enumerate(tokens[:6]):
        if _DEF_BODY_START.match(token):
            if i > 0:
                text = ' '.join(tokens[i:])
            break
    return text.rstrip(' ;,')


def _scrub_root_ids(text: str) -> str:
    """Drop the CDSL entry id glued onto cited roots ('sañj.228458' -> 'sañj')."""
    return _CITED_ROOT.sub(
        lambda m: m.group(0)[: m.start(1) - m.start(0)] + _CDSL_ID.sub("", m.group(1)), text
    )
# --- end copied block -----------------------------------------------------------


def flatten(raw: str) -> str:
    """Flat text from a raw MW XML fragment (tags and markup removed)."""
    raw = _MARKS.sub("", _XML_BOOKKEEPING.sub(" ", raw))
    return _WS.sub(" ", html.unescape(_TAG.sub(" ", raw))).replace("¦", "").strip()


def clean_body(raw: str) -> str:
    """Plain-text gloss from a raw MW ``<body>`` fragment."""
    return _scrub_root_ids(clean_definition(flatten(raw)))


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
        stem = flatten(_field("key2", chunk)).replace("-", "") or key
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
            name = next((n for n in zf.namelist() if n.endswith("mw.xml")), None)
            if name is None:
                raise ValueError(f"no mw.xml inside {path}")
            return zf.read(name).decode("utf-8")
    return path.read_text(encoding="utf-8")


def build(src: Path, out: Path) -> int:
    """Write the SQLite index to ``out``; returns the number of rows.

    Builds into ``<out>.tmp`` and swaps it in with ``os.replace`` once complete,
    so a failed build leaves any existing ``out`` untouched.
    """
    tmp = out.with_name(out.name + ".tmp")
    tmp.unlink(missing_ok=True)
    try:
        con = sqlite3.connect(tmp)
        try:
            con.execute(
                "CREATE TABLE mw (key TEXT, key_stem TEXT, lnum TEXT, page TEXT, "
                "text TEXT, hom TEXT)"
            )
            con.executemany(
                "INSERT INTO mw VALUES (?,?,?,?,?,?)", parse_entries(read_xml(src))
            )
            con.execute("CREATE INDEX mw_key ON mw (key)")
            con.commit()
            n = con.execute("SELECT COUNT(*) FROM mw").fetchone()[0]
        finally:
            con.close()
        os.replace(tmp, out)
        return n
    except BaseException:
        tmp.unlink(missing_ok=True)
        raise


def main(argv: list[str]) -> int:
    if len(argv) != 3:
        print(__doc__)
        return 2
    n = build(Path(argv[1]), Path(argv[2]))
    print(f"wrote {n} rows to {argv[2]}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
