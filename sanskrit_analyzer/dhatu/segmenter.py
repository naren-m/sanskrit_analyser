"""Local, offline Sanskrit word segmenter (replaces the remote Dharmamitra API).

The one job the remote Dharmamitra API performed was **segmentation**: splitting
running verse text — where words are fused by sandhi and samāsa — into individual
padas. Dhātu identification itself is already local via :mod:`vidyut.kosha`
(see :mod:`sanskrit_analyzer.deep_read.kosha_engine`); only word-boundary
detection needed the network.

This module removes that dependency with a **sandhi-aware dynamic-programming
segmenter over the kosha lexicon** — the same architecture as Huet's Sanskrit
Heritage Reader:

1. :func:`vidyut.sandhi.Splitter` enumerates the phonetically legal
   ``(first, second)`` cuts at each position (the sandhi-undo step).
2. :mod:`vidyut.kosha` validates each candidate member as a real pada.
3. A memoized DP finds the fewest-piece all-valid segmentation.

It is *sound* (every returned split is sandhi-consistent and lexically valid),
*complete* (searches all cut positions), and *polynomial* (memoized over
positions). What it does not do by itself is *rank* competing valid parses — that
is a separate concern handled downstream (ByT5 reranker / frequency), see
:mod:`sanskrit_analyzer.dhatu.identifier`.

Vidyut's own packaged segmenter (``cheda.Chedaka``) is deliberately NOT used: it
returns ``data=None`` on real Rāmāyaṇa compounds and mangles otherwise-valid
padas. The low-level ``sandhi.Splitter`` primitive + kosha validation
outperforms it on exactly those cases.
"""

from __future__ import annotations

import logging
from functools import lru_cache
from pathlib import Path

from sanskrit_analyzer.deep_read import kosha_engine

logger = logging.getLogger(__name__)

# A whitespace-delimited token longer than this (in SLP1 chars) is worth trying
# to split as a compound; shorter tokens are almost always a single pada and
# splitting them only invites spurious over-segmentation from short members.
_MIN_SPLIT_LEN = 6


class SegmenterUnavailable(RuntimeError):
    """Raised when the vidyut sandhi/kosha data needed to segment is missing."""


@lru_cache(maxsize=1)
def _splitter():
    """Load the vidyut sandhi splitter from the resolved data bundle."""
    data_dir = kosha_engine.resolve_data_dir()
    if data_dir is None:
        raise SegmenterUnavailable(
            "vidyut data bundle not found; cannot build the sandhi splitter."
        )
    rules = Path(data_dir) / "sandhi" / "rules.csv"
    if not rules.is_file():
        raise SegmenterUnavailable(f"sandhi rules not found at {rules}")
    from vidyut.sandhi import Splitter

    logger.info("Loading vidyut sandhi splitter from %s", rules)
    return Splitter.from_csv(str(rules))


def is_available() -> bool:
    """True if both the kosha and sandhi data needed to segment are present."""
    data_dir = kosha_engine.resolve_data_dir()
    return data_dir is not None and (Path(data_dir) / "sandhi" / "rules.csv").is_file()


def _kosha_valid(slp: str) -> bool:
    """True if ``slp`` (after undoing common final sandhi) is a real pada."""
    kosha = kosha_engine._kosha()
    return any(list(kosha.get(cand)) for cand in kosha_engine.desandhi_candidates(slp))


@lru_cache(maxsize=8192)
def _solve(s: str) -> tuple[str, ...] | None:
    """Fewest-piece segmentation of SLP1 ``s`` into kosha-valid members.

    Returns a tuple of SLP1 members, or ``None`` if no fully-valid segmentation
    exists. The whole string (kept intact) is always a candidate, so a word that
    is itself a single valid pada returns ``(s,)`` rather than being force-split.
    """
    if not s:
        return ()
    best: tuple[str, ...] | None = (s,) if _kosha_valid(s) else None
    splitter = _splitter()
    for i in range(1, len(s)):
        for split in splitter.split_at(s, i):
            first, second = split.first, split.second
            if not first or not second or first == s:
                continue
            if not _kosha_valid(first):
                continue
            rest = _solve(second)
            if rest is None:
                continue
            candidate = (first,) + rest
            if best is None or len(candidate) < len(best):
                best = candidate
    return best


def segment_slp(slp: str) -> list[str]:
    """Segment a single SLP1 token into member padas (SLP1).

    Falls back to the whole token if no valid multi-member split is found, so the
    caller always gets at least the original word back.
    """
    if len(slp) < _MIN_SPLIT_LEN:
        return [slp]
    result = _solve(slp)
    return list(result) if result else [slp]


def segment(text: str) -> list[str] | None:
    """Segment a Devanagari line into member padas, returned as IAST.

    This is the drop-in replacement for the remote Dharmamitra
    ``segment(text) -> list[str] | None`` contract: it returns unsandhied words
    in IAST, ``[]`` for empty input, and ``None`` when the segmenter data is
    unavailable (so the caller can fall back). It never raises for ordinary text.
    """
    if not text or not text.strip():
        return []
    if not is_available():
        return None
    try:
        members: list[str] = []
        for token in kosha_engine.tokenize(text):
            slp = kosha_engine.slp(token)
            for piece in segment_slp(slp):
                iast = kosha_engine.to_iast(piece)
                if iast:
                    members.append(iast)
        return members
    except kosha_engine.VidyutUnavailable:
        return None
    except Exception as exc:  # segmentation is best-effort; never break the caller
        logger.warning("segmentation failed for %r: %s", text, exc)
        return None
