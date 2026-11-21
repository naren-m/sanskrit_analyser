#!/usr/bin/env python3
"""Build the opt-in Apte (AP90) SQLite index read by ``sanskrit_analyzer.lexicon``.

Usage: ``build_apte_index.py --xml <ap90.xml | ap90xml.zip> --out <ap90.sqlite>``

Apte's dictionary (sanskrit-lexicon/AP90) is GPL-3.0, so the package never
bundles it and this script never downloads it: pass a local copy. Writes table
``ap90(key, key_stem, lnum, page, text, hom)`` with an index on ``key``, the
same schema and the same SLP1 body cleaning as the Monier-Williams index
(``build_mw_index.py``, imported rather than copied). Point
``SANSKRIT_AP90_DB`` at the output, or put it at
``~/.sanskrit_analyzer/lexicon/ap90.sqlite``.
"""
from __future__ import annotations

import argparse
import importlib.util
import os
import sqlite3
import sys
import zipfile
from pathlib import Path

LICENCE = "GPL-3.0"

_spec = importlib.util.spec_from_file_location(
    "build_mw_index", Path(__file__).resolve().with_name("build_mw_index.py")
)
_mw = importlib.util.module_from_spec(_spec)
sys.modules.setdefault("build_mw_index", _mw)
_spec.loader.exec_module(_mw)

parse_entries = _mw.parse_entries


def read_xml(path: Path) -> str:
    if path.suffix == ".zip":
        with zipfile.ZipFile(path) as zf:
            name = next((n for n in zf.namelist() if n.endswith("ap90.xml")), None)
            if name is None:
                raise ValueError(f"no ap90.xml inside {path}")
            return zf.read(name).decode("utf-8")
    return path.read_text(encoding="utf-8")


def build(src: Path, out: Path) -> int:
    """Write the SQLite index to ``out``; returns the number of rows.

    Builds into ``<out>.tmp`` and swaps it in once complete, so a failed build
    leaves any existing ``out`` untouched.
    """
    tmp = out.with_name(out.name + ".tmp")
    tmp.unlink(missing_ok=True)
    try:
        con = sqlite3.connect(tmp)
        try:
            con.execute(
                "CREATE TABLE ap90 (key TEXT, key_stem TEXT, lnum TEXT, page TEXT, "
                "text TEXT, hom TEXT)"
            )
            con.executemany(
                "INSERT INTO ap90 VALUES (?,?,?,?,?,?)", parse_entries(read_xml(src))
            )
            con.execute("CREATE INDEX ap90_key ON ap90 (key)")
            con.commit()
            n = con.execute("SELECT COUNT(*) FROM ap90").fetchone()[0]
        finally:
            con.close()
        os.replace(tmp, out)
        return n
    except BaseException:
        tmp.unlink(missing_ok=True)
        raise


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--xml", required=True, type=Path, help="ap90.xml or the zip")
    ap.add_argument("--out", required=True, type=Path, help="output SQLite path")
    args = ap.parse_args(argv)
    n = build(args.xml, args.out)
    print(f"wrote {n} rows to {args.out} (data licence: {LICENCE})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
