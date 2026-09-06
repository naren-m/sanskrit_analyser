"""Optional ByT5 reranker/tagger layer for the dhātu identifier.

The rule-based DP segmenter (:mod:`sanskrit_analyzer.dhatu.segmenter`) is a fast,
deterministic *candidate generator*, but it cannot rank among competing valid
splits nor disambiguate homographs. The locally-cached ByT5 model
(``chronbmm/sanskrit5-multitask``) closes that gap: its combined *SLM* task emits,
in one call, both the segmentation and a coarse part-of-speech tag per member.

:class:`ByT5Adapter` exposes that as two functions the identifier can consume:

* ``segment(text) -> list[str] | None`` — ByT5's own IAST word split (a
  higher-recall alternative to the rule DP);
* ``pos_hint(word) -> "noun" | "verb" | None`` — the POS the SLM task assigned to
  that word, used by :func:`sanskrit_analyzer.dhatu.identifier.rank_analyses` to
  pick the right reading (e.g. रामः → noun, not the finite verb √rā).

The model is loaded lazily and only on first use, so importing this module is
free. When transformers/torch or the model are unavailable, everything degrades
to ``None`` and the caller falls back to the pure-rule path.
"""

from __future__ import annotations

import logging
from functools import lru_cache

logger = logging.getLogger(__name__)


class ByT5Adapter:
    """Lazy adapter over :class:`LocalByT5Engine` exposing segment + POS hints.

    A single SLM call per line is cached so ``segment`` and ``pos_hint`` for the
    same text do not run the model twice.
    """

    def __init__(self, engine=None) -> None:
        self._engine = engine
        self._loaded = engine is not None
        # The most recent line's ByT5 analysis; see _analyze for why only one.
        self._cached_text: str | None = None
        self._pos: dict[str, str] = {}
        self._segments: list[str] = []

    def _ensure_engine(self):
        if not self._loaded:
            from sanskrit_analyzer.engines.local_byt5_engine import LocalByT5Engine

            try:
                self._engine = LocalByT5Engine(load_on_init=True)
            except Exception as exc:  # torch/transformers/model missing
                logger.warning("ByT5 adapter unavailable: %s", exc)
                self._engine = None
            self._loaded = True
        return self._engine

    def is_available(self) -> bool:
        engine = self._ensure_engine()
        return bool(engine and engine.is_available)

    def _analyze(self, text: str) -> None:
        """Run and cache the ByT5 SLM segmentation + POS tags for ``text``.

        Only the most recent line is kept: ``pos_hint`` is asked about words of
        the line just segmented, and keeping older lines would both grow without
        bound and let a POS tag from an earlier line leak onto a homograph here.
        """
        self._cached_text = None
        self._pos = {}
        self._segments = []

        engine = self._ensure_engine()
        if engine is None or not engine.is_available:
            return

        result = _run_engine(engine, text)
        segments = [s for s in (getattr(result, "segments", None) or []) if s.surface]
        self._cached_text = text
        self._pos = {s.surface: s.pos for s in segments if s.pos}
        self._segments = [s.surface for s in segments]

    def segment(self, text: str) -> list[str] | None:
        """ByT5 segmentation of ``text`` into IAST members, or ``None``."""
        if not text or not text.strip():
            return []
        if self._cached_text != text:
            self._analyze(text)
        return self._segments or None

    def pos_hint(self, word: str) -> str | None:
        """Coarse POS (``"noun"``/``"verb"``) ByT5 assigned to ``word``, if seen.

        Only ``noun`` and ``verb`` are surfaced — the two classes
        :func:`rank_analyses` acts on; adjectives/indeclinables return ``None``
        (no ranking preference).
        """
        pos = self._pos.get(word)
        return pos if pos in ("noun", "verb") else None


def _run_engine(engine, text: str):
    """Call the engine synchronously whether or not an event loop is running.

    ``LocalByT5Engine`` exposes ``analyze_sync``; other engines (and test fakes)
    only have the async ``analyze``. ``asyncio.run`` raises inside a running loop
    (FastAPI/MCP callers), so in that case the coroutine runs on a helper thread.
    """
    sync = getattr(engine, "analyze_sync", None)
    if sync is not None:
        return sync(text)

    import asyncio
    import concurrent.futures

    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(engine.analyze(text))
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(lambda: asyncio.run(engine.analyze(text))).result()


@lru_cache(maxsize=1)
def get_shared_adapter() -> ByT5Adapter:
    """Return a process-wide :class:`ByT5Adapter` so the ~2 GB model loads once.

    Used by the default-on segmentation path; callers that want an isolated
    instance can still construct :class:`ByT5Adapter` directly.
    """
    return ByT5Adapter()
