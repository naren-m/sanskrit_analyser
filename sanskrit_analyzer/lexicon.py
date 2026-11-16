"""Layer B lexicon: lookup over the bundled CDSL dictionaries.

A sixth source, Monier-Williams ("mw"), is read from SQLite; see
:func:`resolve_mw_db`.

Five Cologne Digital Sanskrit Dictionaries tables live in
``data/vyutpatti/`` (see the README there). They share a SLP1 ``key`` column
but not a schema: Śabdakalpadruma and Vācaspatyam are etymology tables with
15 and 7 columns, while the other three are gloss tables shaped
``key, lnum, page, text``. This module normalises all five to :class:`Entry`,
keeping the source-specific columns in ``Entry.fields`` so callers never have
to branch on the source.

The TSVs are ~20 MB and are excluded from the wheel (see ``pyproject.toml``),
so :func:`is_available` may be False for a pip-installed copy. Callers should
check it rather than assume; ``scripts/build_layerb.py`` regenerates the data.
"""
from __future__ import annotations

import csv
import bisect
import logging
import os
import sqlite3
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import NamedTuple

from sanskrit_analyzer.utils.normalize import normalize_slp1

logger = logging.getLogger(__name__)


class _Source(NamedTuple):
    """How one Layer B table is read into :class:`Entry`."""

    filename: str
    name: str                    # human-readable, e.g. "Śabdakalpadruma"
    text_col: str                # column holding the gloss or etymology body
    fallback_col: str | None     # used when ``text_col`` is empty for a row
    sqlite: bool = False         # read from the SQLite resolver, not the TSV dir


_SOURCES: dict[str, _Source] = {
    "skd": _Source("vyutpatti-skd.tsv", "Śabdakalpadruma", "vyutpatti", "nirvacana"),
    "vcp": _Source("vyutpatti-vcp.tsv", "Vācaspatyam", "head_segment", None),
    "krdanta": _Source("krdantarupamala.tsv", "Kṛdantarūpamālā", "text", None),
    "abhidhanaratnamala": _Source(
        "abhidhanaratnamala.tsv", "Abhidhānaratnamālā", "text", None
    ),
    "abhidhanacintamani": _Source(
        "abhidhanacintamani.tsv", "Abhidhānacintāmaṇi", "text", None
    ),
    "mw": _Source("mw.sqlite", "Monier-Williams", "text", None, sqlite=True),
}
_LAYERB = {k: v for k, v in _SOURCES.items() if not v.sqlite}

MW_ACKNOWLEDGEMENT = (
    "Monier-Williams Sanskrit-English Dictionary (1899), digitised by the "
    "Cologne Digital Sanskrit Dictionaries, Institut für Indologie und "
    "Südasienforschung, Universität zu Köln (https://www.sanskrit-lexicon.uni-koeln.de)"
)
MW_LICENCE = "CC BY-SA 4.0"


# Columns that become Entry attributes rather than staying in ``fields``.
_PROMOTED = {"key", "page", "lnum"}


@dataclass(frozen=True)
class Entry:
    """One dictionary entry, normalised across the five Layer B tables."""

    source: str                              # e.g. "skd"
    source_name: str                         # e.g. "Śabdakalpadruma"
    key: str                                 # SLP1 headword
    text: str                                # gloss or etymology body
    page: str | None = None
    fields: dict[str, str] = field(default_factory=dict)
    acknowledgement: str | None = None       # provenance string, MW only
    licence: str | None = None               # e.g. "CC BY-SA 4.0", MW only


def resolve_data_dir() -> Path | None:
    """Find a directory holding the Layer B TSVs, or None.

    Order: ``SANSKRIT_LAYERB_DIR`` env, the in-package ``data/vyutpatti``
    (present for a repo checkout or editable install), then
    ``~/.sanskrit_analyzer/vyutpatti``. Mirrors ``vidyut_data.resolve_data_dir``
    so the two big external datasets are discovered the same way.
    """
    candidates: list[Path] = []
    env = os.environ.get("SANSKRIT_LAYERB_DIR")
    if env:
        candidates.append(Path(env).expanduser())
    candidates.append(Path(__file__).resolve().parent / "data" / "vyutpatti")
    candidates.append(Path.home() / ".sanskrit_analyzer" / "vyutpatti")

    for c in candidates:
        if any((c / spec.filename).is_file() for spec in _LAYERB.values()):
            return c
    return None


def resolve_mw_db() -> Path | None:
    """Find the Monier-Williams SQLite file, or None.

    Order: ``SANSKRIT_MW_DB`` env, the in-package ``data/lexicon/mw.sqlite``,
    then ``~/.sanskrit_analyzer/lexicon/mw.sqlite``. Separate from
    :func:`resolve_data_dir`, which only serves the Layer B TSVs.
    """
    candidates: list[Path] = []
    env = os.environ.get("SANSKRIT_MW_DB")
    if env:
        candidates.append(Path(env).expanduser())
    candidates.append(Path(__file__).resolve().parent / "data" / "lexicon" / "mw.sqlite")
    candidates.append(Path.home() / ".sanskrit_analyzer" / "lexicon" / "mw.sqlite")
    return next((c for c in candidates if c.is_file()), None)


def _spec(source: str) -> _Source:
    """The table spec for ``source``, or a KeyError naming the valid ids."""
    if source not in _SOURCES:
        raise KeyError(f"unknown Layer B source {source!r}; have {sorted(_SOURCES)}")
    return _SOURCES[source]


def is_available(source: str | None = None) -> bool:
    """True if the Layer B data is present (does not load it)."""
    if source is not None and _spec(source).sqlite:
        return resolve_mw_db() is not None
    data_dir = resolve_data_dir()
    if data_dir is None:
        return False
    if source is None:
        return True
    return (data_dir / _spec(source).filename).is_file()


def available_sources() -> list[str]:
    return sorted(s for s in _SOURCES if is_available(s))


@lru_cache(maxsize=len(_LAYERB))
def _index(source: str) -> dict[str, tuple[Entry, ...]]:
    """``key -> entries`` for one TSV source, loaded once. A key may repeat."""
    spec = _spec(source)
    if spec.sqlite:
        return {}
    data_dir = resolve_data_dir()
    if data_dir is None:
        return {}
    path = data_dir / spec.filename
    if not path.is_file():
        return {}

    index: dict[str, list[Entry]] = {}
    with path.open(encoding="utf-8", newline="") as fh:
        for row in csv.DictReader(fh, delimiter="\t"):
            key = (row.get("key") or "").strip()
            if not key:
                continue
            text = (row.get(spec.text_col) or "").strip()
            if not text and spec.fallback_col:
                text = (row.get(spec.fallback_col) or "").strip()
            index.setdefault(key, []).append(
                Entry(
                    source=source,
                    source_name=spec.name,
                    key=key,
                    text=text,
                    page=(row.get("page") or "").strip() or None,
                    fields={
                        k: v.strip()
                        for k, v in row.items()
                        if k and k not in _PROMOTED and v and v.strip()
                    },
                )
            )
    logger.info("Loaded %d Layer B keys from %s", len(index), spec.filename)
    return {k: tuple(v) for k, v in index.items()}


def _mw_connect() -> sqlite3.Connection | None:
    path = resolve_mw_db()
    if path is None:
        return None
    return sqlite3.connect(f"{path.resolve().as_uri()}?mode=ro", uri=True)


def _mw_lookup(key: str) -> list[Entry]:
    con = _mw_connect()
    if con is None:
        return []
    try:
        rows = con.execute(
            "SELECT key, key_stem, lnum, page, text, hom FROM mw "
            "WHERE key = ? ORDER BY rowid",
            (key,),
        ).fetchall()
    finally:
        con.close()
    spec = _SOURCES["mw"]
    out = []
    for k, stem, lnum, page, text, hom in rows:
        extra = {"lnum": lnum, "hom": hom, "key_stem": stem}
        out.append(
            Entry(
                source="mw",
                source_name=spec.name,
                key=k,
                text=text,
                page=page or None,
                fields={n: str(v) for n, v in extra.items() if v},
                acknowledgement=MW_ACKNOWLEDGEMENT,
                licence=MW_LICENCE,
            )
        )
    return out


def _mw_prefix(partial: str, limit: int) -> list[str]:
    con = _mw_connect()
    if con is None:
        return []
    try:
        rows = con.execute(
            "SELECT DISTINCT key FROM mw WHERE key >= ? AND key < ? "
            "ORDER BY key LIMIT ?",
            (partial, partial + "\U0010ffff", limit),
        ).fetchall()
    finally:
        con.close()
    return [r[0] for r in rows]


@lru_cache(maxsize=len(_LAYERB))
def _sorted_keys(source: str) -> list[str]:
    return sorted(_index(source))


def lookup(word: str, sources: list[str] | None = None) -> list[Entry]:
    """Entries for ``word`` across the requested sources (all by default).

    ``word`` may be Devanāgarī, IAST or SLP1; it is normalised to SLP1, which is
    how every key is stored. ``"mw"`` yields no entries when its SQLite file is
    absent.
    """
    key = normalize_slp1(word).strip()
    if not key:
        return []
    wanted = sources if sources is not None else sorted(_SOURCES)
    out: list[Entry] = []
    for source in wanted:
        if _spec(source).sqlite:
            out.extend(_mw_lookup(key))
        else:
            out.extend(_index(source).get(key, ()))
    return out


def prefix(
    partial: str, limit: int = 20, sources: list[str] | None = None
) -> list[str]:
    """Sorted, distinct SLP1 keys starting with ``partial``, at most ``limit``."""
    stem = normalize_slp1(partial).strip()
    wanted = sources if sources is not None else sorted(_SOURCES)
    specs = [(s, _spec(s)) for s in wanted]  # raises KeyError on an unknown id
    if not stem or limit <= 0:
        return []
    keys: set[str] = set()
    for source, spec in specs:
        if spec.sqlite:
            keys.update(_mw_prefix(stem, limit))
            continue
        sk = _sorted_keys(source)
        start = bisect.bisect_left(sk, stem)
        for k in sk[start : start + limit]:
            if not k.startswith(stem):
                break
            keys.add(k)
    return sorted(keys)[:limit]
