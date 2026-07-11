"""Deep Read orchestration: a Sanskrit line -> per-pada dhātu analyses.

``DeepRead`` is the public entry point. It keeps three analysis paths and the
same fallthrough order the facility shipped with:

1. ``prefer_analyzer`` → the high-level :class:`sanskrit_analyzer.Analyzer`
   (real word splitting; opt-in, currently degrades on long verses).
2. ``use_dharmamitra`` → Dharmamitra ByT5 segmentation + per-word kosha
   enrichment (the hybrid: ByT5 segments, kosha enriches).
3. fallback → the local :mod:`~sanskrit_analyzer.deep_read.kosha_engine`
   (whitespace/danda tokenization + de-sandhi kosha lookup).

The internal ``_analyze_*`` methods produce the legacy plain-dict shape verbatim
(so behavior is byte-identical to the pre-promotion ramayanam service); the
public methods wrap them into the typed :class:`DeepReadResult` model.

Scripture-agnostic: corpus / verse-by-id lookups stay in the consuming project.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from sanskrit_analyzer.deep_read import dharmamitra_segmenter as dseg
from sanskrit_analyzer.deep_read import kosha_engine as engine
from sanskrit_analyzer.deep_read.models import DeepReadResult

logger = logging.getLogger(__name__)

_DHARMAMITRA_NOTES = [
    "Segmentation by the Dharmamitra ByT5 model (real sandhi/compound splitting, "
    "e.g. इक्ष्वाकुवंशप्रभवो → ikṣvāku · vaṃśa · prabhava); per-word dhatu/meaning "
    "by vidyut.kosha. Hybrid: ByT5 segments, kosha enriches.",
    "Dhatu meaning artha_sa is authoritative (Sanskrit); english is best-effort.",
]

_NOTES = [
    "Word boundaries are whitespace/danda based; sandhi-aware compound "
    "splitting is unavailable (vidyut.cheda bundle incomplete).",
    "Multiple analyses per word are candidates, not disambiguated. The "
    "authoritative dhatu meaning is artha_sa (Sanskrit); english is best-effort.",
]

_ANALYZER_NOTES = [
    "Segmentation and dhatu attribution come from sanskrit_analyzer's Analyzer "
    "(real word splitting). One best-parse analysis is shown per pada.",
    "Morphology is engine-dependent and may be empty; dhatu meanings are "
    "best-effort English glosses.",
]


class DeepRead:
    """Orchestrates the Deep Read analysis paths over a shared kosha engine.

    Parameters
    ----------
    config:
        Optional :class:`sanskrit_analyzer.Config`. Only consulted for the
        ``prefer_analyzer`` path, where a :class:`sanskrit_analyzer.Analyzer` is
        built lazily. The local kosha + Dharmamitra paths need no config and
        preserve the facility's current defaults.
    """

    def __init__(self, config: Any | None = None) -> None:
        self._config = config
        self._analyzer = None  # lazily constructed for the Analyzer path

    # ------------------------------------------------------------------ public
    def analyze(
        self, text: str, prefer_analyzer: bool = False, use_dharmamitra: bool = True
    ) -> DeepReadResult:
        """Analyze a raw Sanskrit line into typed tokens with candidate dhātus.

        Uses the local ``vidyut.kosha`` + de-sandhi engine by default: on real
        running-text verses it keeps padas whole (रामो→राम, नियतात्मा→niyatAtman)
        and labels true compounds honestly. The upstream ``Analyzer`` path
        (``prefer_analyzer=True``) currently degrades long verses — its cheda
        fallback fragments and transliteration-corrupts sandhi'd padas — so it
        stays opt-in until that is fixed (see issues #328–331). It is ready to
        become the default once it beats the local engine on the Rāmāyaṇa gold
        eval.
        """
        return DeepReadResult.from_legacy(
            self._analyze_text(text, prefer_analyzer, use_dharmamitra)
        )

    def analyze_via_dharmamitra(self, text: str) -> DeepReadResult | None:
        """Dharmamitra ByT5 segmentation + kosha enrichment, or ``None``."""
        d = self._analyze_via_dharmamitra(text)
        return DeepReadResult.from_legacy(d) if d is not None else None

    def analyze_via_analyzer(self, text: str) -> DeepReadResult | None:
        """Upstream :class:`Analyzer` segmentation path, or ``None``."""
        d = self._analyze_via_analyzer(text)
        return DeepReadResult.from_legacy(d) if d is not None else None

    # ------------------------------------------------------- dict-shaped core
    def _analyze_text(
        self, text: str, prefer_analyzer: bool = False, use_dharmamitra: bool = True
    ) -> dict[str, Any]:
        text = (text or "").strip()

        if prefer_analyzer:
            via_analyzer = self._analyze_via_analyzer(text)
            if via_analyzer is not None and via_analyzer.get("tokens"):
                return via_analyzer

        # Primary: Dharmamitra ByT5 segmentation + kosha dhatu enrichment. Falls
        # through to the local kosha-only engine if the service is unreachable
        # (or when disabled, e.g. in offline unit tests).
        if use_dharmamitra:
            via_dm = self._analyze_via_dharmamitra(text)
            if via_dm is not None and via_dm.get("tokens"):
                return via_dm

        pieces = engine.tokenize(text)
        try:
            tokens = [engine.analyze_word(tok) for tok in pieces]
        except engine.VidyutUnavailable as exc:
            # Dharmamitra unreachable AND the vidyut bundle absent: degrade to
            # segmentation-only unknown tokens instead of crashing the request.
            logger.warning(
                "vidyut kosha unavailable; degrading to unknown tokens: %s", exc
            )
            return {
                "input": text,
                "slp1": None,
                "engine": "unavailable",
                "tokens": [
                    {
                        "surface": piece,
                        "slp1": None,
                        "resolved": False,
                        "analyses": [{"kind": "unknown", "lemma": None,
                                      "dhatu": None, "morphology": {}}],
                    }
                    for piece in pieces
                ],
                "notes": [
                    "vidyut.kosha is unavailable, so words could not be analyzed; "
                    "only whitespace/danda segmentation is shown.",
                ],
            }
        slp1 = None
        try:
            slp1 = engine.slp(text) if text else ""
        except Exception:  # whole-line transliteration is only a convenience
            slp1 = None
        return {
            "input": text,
            "slp1": slp1,
            "engine": "vidyut-kosha",
            "tokens": tokens,
            "notes": _NOTES,
        }

    def _analyze_via_dharmamitra(self, text: str) -> dict[str, Any] | None:
        """Segment with Dharmamitra ByT5, enrich each word with vidyut.kosha.

        Returns the standard token shape, or ``None`` if the segmenter is
        unavailable (so the caller falls back to the local engine).
        """
        text = (text or "").strip()
        if not text:
            return None
        words_iast = dseg.segment(text)
        if not words_iast:
            return None

        tokens: list[dict[str, Any]] = []
        for w_iast in words_iast:
            try:
                surface_dev = dseg.iast_to_devanagari(w_iast)
            except Exception:
                surface_dev = w_iast
            try:
                tok = engine.analyze_word(surface_dev)
            except Exception:  # kosha unavailable, etc. — keep the segmentation
                tok = {
                    "surface": surface_dev,
                    "slp1": None,
                    "resolved": False,
                    "analyses": [{"kind": "unknown", "lemma": None,
                                  "dhatu": None, "morphology": {}}],
                }
            tokens.append(tok)

        try:
            slp1 = engine.slp(text)
        except Exception:
            slp1 = None
        return {
            "input": text,
            "slp1": slp1,
            "engine": "dharmamitra+kosha",
            "tokens": tokens,
            "notes": _DHARMAMITRA_NOTES,
        }

    def _analyze_via_analyzer(self, text: str) -> dict[str, Any] | None:
        """Analyze ``text`` with the upstream :class:`Analyzer`.

        Returns a dict with the same top-level shape as :meth:`_analyze_text`
        (so the Deep Read page keeps working unchanged), or ``None`` if the
        Analyzer is unavailable or produces nothing usable (the caller then
        falls back to the local kosha engine).

        The Analyzer segments short lines well, but on a long running verse it
        can return the whole line unsplit as one garbled token. So we first
        analyze the whole line; if that did *not* segment (one oversized token
        for a multi-word input), we fall back to analyzing each whitespace/danda
        pada on its own and flatten the resulting base_words into Deep Read
        tokens.

        Unlike the original ramayanam service, this calls
        :class:`sanskrit_analyzer.Analyzer` directly — the facade must never
        import the consuming project.
        """
        text = (text or "").strip()
        if not text:
            return None

        try:
            from sanskrit_analyzer import AnalysisMode
        except Exception as exc:  # pragma: no cover - import guard
            logger.debug("sanskrit_analyzer.AnalysisMode unavailable: %s", exc)
            return None

        pieces = engine.tokenize(text) or [text]

        try:
            whole = self._analyze_sloka_sync(text, AnalysisMode.EDUCATIONAL)
            base_words = list(_iter_base_words(whole))
            if _well_segmented(base_words, len(pieces)):
                tokens = [_token_from_base_word(bw) for bw in base_words]
            else:
                # Whole-line analysis collapsed the input; analyze each pada.
                tokens = []
                for piece in pieces:
                    tree = self._analyze_sloka_sync(piece, AnalysisMode.EDUCATIONAL)
                    for base_word in _iter_base_words(tree):
                        tokens.append(_token_from_base_word(base_word))
        except Exception as exc:
            logger.debug("Analyzer path failed, falling back: %s", exc)
            return None

        if not tokens:
            return None

        slp1 = None
        try:
            slp1 = engine.slp(text)
        except Exception:
            slp1 = None

        return {
            "input": text,
            "slp1": slp1,
            "engine": "sanskrit-analyzer",
            "tokens": tokens,
            "notes": _ANALYZER_NOTES,
        }

    # ------------------------------------------------------- Analyzer plumbing
    def _get_analyzer(self):
        """Lazily build the high-level Analyzer (only for the analyzer path)."""
        if self._analyzer is None:
            from sanskrit_analyzer import Analyzer, Config

            self._analyzer = Analyzer(self._config or Config())
        return self._analyzer

    def _analyze_sloka_sync(self, text: str, mode: Any):
        """Synchronous wrapper around ``Analyzer.analyze`` (POC/offline use).

        ``asyncio.run`` raises if called from within a running event loop (e.g.
        an async server). When a loop is already running we run the coroutine on
        a dedicated worker thread so the analyzer path still works there.
        """
        analyzer = self._get_analyzer()

        def _run() -> Any:
            return asyncio.run(analyzer.analyze(text, mode=mode))

        try:
            asyncio.get_running_loop()
        except RuntimeError:
            # No running loop in this thread — safe to drive one directly.
            return _run()

        import concurrent.futures

        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            return pool.submit(_run).result()


# --------------------------------------------------------------------------
# Analyzer-path helpers (module-level; no per-instance state).
# --------------------------------------------------------------------------

def _dhatu_block(dhatu_info: Any) -> dict[str, Any] | None:
    """Build the JSON dhatu block from a sanskrit_analyzer ``DhatuInfo``."""
    if dhatu_info is None:
        return None
    root = getattr(dhatu_info, "dhatu", None)
    if not root:
        return None

    try:
        root_dev = engine.to_devanagari(root)
    except Exception:
        root_dev = None

    # ``gana`` is an int in this engine build; older builds may give a name.
    raw_gana = getattr(dhatu_info, "gana", None)
    if isinstance(raw_gana, int):
        gana_num = raw_gana
    else:
        gana_num = engine.gana_to_number(raw_gana) if raw_gana else None
    gana = getattr(dhatu_info, "gana_name", None) or (
        raw_gana if isinstance(raw_gana, str) else None
    )

    artha_sa = getattr(dhatu_info, "artha_sa", None)
    artha_iast = getattr(dhatu_info, "artha_iast", None)

    english = engine.english_for_root(root)
    if not english:
        # Fall back to the engine's own meaning if our curated map misses it.
        english = getattr(dhatu_info, "primary_meaning", None)
        if not english:
            meanings = getattr(dhatu_info, "meanings", None) or []
            english = meanings[0] if meanings else None

    return {
        "root": root,
        "root_dev": root_dev,
        "gana": gana,
        "gana_num": gana_num,
        "artha_sa": artha_sa,
        "artha_iast": artha_iast,
        "english": english,
    }


def _morphology_dict(base_word: Any) -> dict[str, str]:
    """Normalise a base_word's morphology into a flat str->str dict."""
    morph = getattr(base_word, "morphology", None)
    if morph is None:
        return {}
    if hasattr(morph, "to_dict"):
        try:
            raw = morph.to_dict()
        except Exception:
            return {}
    elif isinstance(morph, dict):
        raw = morph
    else:
        return {}
    out: dict[str, str] = {}
    for key, val in (raw or {}).items():
        if val is None:
            continue
        # Normalise enum-like values (e.g. PartOfSpeech.NOUN) to short strings.
        out[str(key)] = str(getattr(val, "value", val))
    return out


def _classify(base_word: Any, dhatu_block: dict[str, Any] | None) -> str:
    """Map a base_word onto the Deep Read ``kind`` vocabulary."""
    morph = _morphology_dict(base_word)
    pos = (morph.get("pos") or morph.get("part_of_speech") or "").lower()

    if pos in ("verb", "tinanta"):
        return "verb"
    if pos in ("indeclinable", "particle", "avyaya", "adverb"):
        return "indeclinable"

    has_dhatu = dhatu_block is not None
    is_verb_derived = bool(getattr(base_word, "is_verb_derived", False))

    if has_dhatu and is_verb_derived:
        # A finite verb form with no explicit POS in this engine build.
        return "verb"
    if has_dhatu:
        return "derived"
    if getattr(base_word, "lemma", None):
        return "nominal"
    return "unknown"


def _slp1_of(base_word: Any) -> str | None:
    """Best-effort SLP1 string for a base_word (surface form preferred)."""
    surface = getattr(base_word, "surface_form", None)
    if surface:
        # surface_form is already SLP1 in this engine; keep as-is.
        return surface
    scripts = getattr(base_word, "scripts", None)
    return getattr(scripts, "slp1", None) if scripts is not None else None


def _token_from_base_word(base_word: Any) -> dict[str, Any]:
    lemma = getattr(base_word, "lemma", None)
    dhatu_block = _dhatu_block(getattr(base_word, "dhatu", None))
    analysis = {
        "kind": _classify(base_word, dhatu_block),
        "lemma": lemma,
        "dhatu": dhatu_block,
        "morphology": _morphology_dict(base_word),
    }
    slp1 = _slp1_of(base_word)
    # The /deep-read page renders ``surface`` in a Devanagari span; surface_form
    # from the Analyzer is SLP1, so transliterate it back for display.
    surface = None
    if slp1:
        try:
            surface = engine.to_devanagari(slp1)
        except Exception:
            surface = slp1
    return {
        "surface": surface,
        "slp1": slp1,
        "resolved": bool(lemma or dhatu_block),
        "analyses": [analysis],
    }


def _iter_base_words(tree: Any):
    parse = getattr(tree, "best_parse", None)
    if parse is None:
        forest = getattr(tree, "parse_forest", None) or []
        parse = forest[0] if forest else None
    if parse is None:
        return
    for sandhi_group in getattr(parse, "sandhi_groups", None) or []:
        for base_word in getattr(sandhi_group, "base_words", None) or []:
            yield base_word


def _well_segmented(base_words: list[Any], n_input_words: int) -> bool:
    """Heuristic: did whole-line analysis actually segment the input?

    A multi-word input that comes back as a single (often oversized) base_word
    means the Analyzer failed to split it; in that case we re-run per pada.
    """
    if not base_words:
        return False
    if n_input_words <= 1:
        return True
    if len(base_words) < n_input_words:
        return False
    # No single token should swallow the whole line.
    longest = max(len(getattr(bw, "surface_form", "") or "") for bw in base_words)
    return longest <= 20
