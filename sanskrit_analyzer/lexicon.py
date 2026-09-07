"""Layer B lexicon: lookup over the bundled CDSL dictionaries.

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
import logging
import os
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
}


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
        if any((c / spec.filename).is_file() for spec in _SOURCES.values()):
            return c
    return None


def _spec(source: str) -> _Source:
    """The table spec for ``source``, or a KeyError naming the valid ids."""
    if source not in _SOURCES:
        raise KeyError(f"unknown Layer B source {source!r}; have {sorted(_SOURCES)}")
    return _SOURCES[source]


def is_available(source: str | None = None) -> bool:
    """True if the Layer B data is present (does not load it)."""
    data_dir = resolve_data_dir()
    if data_dir is None:
        return False
    if source is None:
        return True
    return (data_dir / _spec(source).filename).is_file()


def available_sources() -> list[str]:
    return sorted(s for s in _SOURCES if is_available(s))


@lru_cache(maxsize=len(_SOURCES))
def _index(source: str) -> dict[str, tuple[Entry, ...]]:
    """``key -> entries`` for one source, loaded once. A key may repeat."""
    spec = _spec(source)
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


def lookup(word: str, sources: list[str] | None = None) -> list[Entry]:
    """Entries for ``word`` across the requested sources (all by default).

    ``word`` may be Devanāgarī, IAST or SLP1; it is normalised to SLP1, which is
    how every Layer B key is stored.
    """
    key = normalize_slp1(word).strip()
    if not key:
        return []
    wanted = sources if sources is not None else sorted(_SOURCES)
    out: list[Entry] = []
    for source in wanted:
        # _index() rejects an unknown source id before touching any data.
        out.extend(_index(source).get(key, ()))
    return out
