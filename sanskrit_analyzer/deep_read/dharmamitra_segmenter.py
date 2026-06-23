"""Dharmamitra ByT5 segmentation for the Deep Read POC.

Why this exists: vidyut-cheda (and the local kosha engine) cannot split Sanskrit
compounds / sandhi-joined padas in running verse text (इक्ष्वाकुवंशप्रभवो,
द्युतिमान्धृतिमान्). The Dharmamitra ByT5-Sanskrit model does this well — but only
when fed *romanized* (IAST) text, and only via its current HTTP API contract
(field ``texts``; response ``{"results": ["w1_w2_..._"]}``). The bundled
``dharmamitra-sanskrit-grammar`` package is stale (sends ``input_sentence`` +
Devanagari → 422 / garbage), which is why sanskrit_analyzer's ensemble silently
ran on vidyut alone.

This module talks to the API directly with the correct contract, returns the
unsandhied word segmentation, and leaves per-word dhatu/lemma/morphology to
``kosha_engine`` (the hybrid: ByT5 segments, kosha enriches).

Note: the endpoint is an *external* public service. It is configurable via
``DHARMAMITRA_API_URL`` and used only for offline/POC analysis — NOT the public
Guru path. Callers must treat a failure as "unavailable" and fall back.
"""

from __future__ import annotations

import logging
import os
import re

import requests

from vidyut.lipi import Scheme, transliterate

logger = logging.getLogger(__name__)

DHARMAMITRA_API_URL = os.environ.get(
    "DHARMAMITRA_API_URL", "https://dharmamitra.org/api/tagging/"
)
_TIMEOUT = float(os.environ.get("DHARMAMITRA_TIMEOUT", "30"))

# Strip dandas, verse numbers, and punctuation before romanizing — otherwise
# "।।1.1.8।।" leaks into the IAST and the ByT5 model drops surrounding words.
_NON_WORD_RE = re.compile(r"[।॥|/0-9०-९.,;:!?()\[\]\"'–—-]+")


def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", _NON_WORD_RE.sub(" ", text)).strip()


def dev_to_iast(text: str) -> str:
    return transliterate(text, Scheme.Devanagari, Scheme.Iast)


def iast_to_devanagari(word: str) -> str:
    return transliterate(word, Scheme.Iast, Scheme.Devanagari)


def _parse_results(raw: str) -> list[str]:
    """Parse one ``results`` string like ``"9 ikṣvāku_vaṃśa_..._"`` into words.

    The API prefixes a per-sentence marker token (observed as ``"9 "`` or
    ``"R "`` — it varies and is not a real word) separated by a space from the
    ``_``-joined unsandhied words. Strip that marker whenever the pre-space chunk
    is a single token (contains no ``_``), then split on ``_``.
    """
    raw = (raw or "").strip()
    head, sep, tail = raw.partition(" ")
    if sep and "_" not in head:  # leading marker (e.g. "9"/"R"), not a real word
        raw = tail
    return [w for w in raw.split("_") if w]


def segment(text_devanagari: str) -> list[str] | None:
    """Return unsandhied words (in IAST) for a Devanagari line via dharmamitra.

    Returns ``None`` if the service is unreachable or returns nothing usable, so
    the caller can fall back to a local engine. Never raises.
    """
    text = _clean(text_devanagari or "")
    if not text:
        return []
    try:
        iast = dev_to_iast(text)
    except Exception as exc:  # transliteration failure → let caller fall back
        logger.warning("dev->iast failed for deep-read segmentation: %s", exc)
        return None
    try:
        resp = requests.post(
            DHARMAMITRA_API_URL,
            json={"texts": [iast], "mode": "unsandhied", "human_readable_tags": True},
            timeout=_TIMEOUT,
        )
        resp.raise_for_status()
        results = resp.json().get("results") or []
    except Exception as exc:  # network/HTTP/JSON — treat as unavailable
        logger.warning("dharmamitra segmentation unavailable: %s", exc)
        return None
    if not results:
        return None
    words = _parse_results(results[0])
    if not words:
        return None

    # Sanity guard: the external ByT5 API occasionally returns degenerate output
    # (e.g. drops all but the last word) on short inputs with a leading long
    # compound. Reject when the segmentation covers far less text than the input
    # (sandhi-splitting changes characters but should not lose most of them), so
    # the caller falls back to the local engine instead of showing garbage.
    input_chars = len(iast.replace(" ", ""))
    seg_chars = len("".join(words))
    if input_chars and seg_chars / input_chars < 0.6:
        logger.warning(
            "dharmamitra segmentation looks degenerate (%d->%d chars); "
            "falling back", input_chars, seg_chars
        )
        return None
    return words
