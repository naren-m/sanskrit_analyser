"""Generic, offline dhātu (verbal root) identifier.

Ties together the local pieces that replace the remote Dharmamitra API:

* segmentation — :mod:`sanskrit_analyzer.dhatu.segmenter` (sandhi-aware DP over
  the kosha lexicon), with a plain-whitespace floor when the sandhi data is
  unavailable;
* dhātu identification — :func:`kosha_engine.analyze_word` (``vidyut.kosha``),
  already fully local;
* ranking — :func:`rank_analyses`, which fixes homograph misfires such as
  ``रामः`` being read as the finite verb √rā rather than the noun राम.

Everything runs offline against the ``~/.vidyut-data`` bundle; no network.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Callable

from sanskrit_analyzer.deep_read import kosha_engine
from sanskrit_analyzer.dhatu import segmenter

logger = logging.getLogger(__name__)

# A finite-verb reading built on a very short root (rā, i, as, ā, ...) is the
# usual culprit when a common noun (रामः → rā-maḥ) is misread as a verb. When a
# nominal reading of the same form also exists, prefer the nominal.
_SHORT_ROOT_LEN = 2


@dataclass
class TokenResult:
    """Identification result for one segmented pada."""

    surface: str  # the Devanagari member as segmented
    slp1: str | None
    resolved: bool
    analyses: list[dict[str, Any]]  # ranked; each has kind/lemma/dhatu/morphology

    @property
    def dhatu(self) -> dict[str, Any] | None:
        """The root of the top-ranked analysis, if any."""
        for a in self.analyses:
            if a.get("dhatu"):
                return a["dhatu"]
        return None

    def to_dict(self) -> dict[str, Any]:
        return {
            "surface": self.surface,
            "slp1": self.slp1,
            "resolved": self.resolved,
            "analyses": self.analyses,
        }


def rank_analyses(
    analyses: list[dict[str, Any]], pos_hint: str | None = None
) -> list[dict[str, Any]]:
    """Re-rank kosha analyses to surface the most plausible reading first.

    Two tiers:

    * **POS hint (preferred):** when a segmenter/tagger supplies a coarse POS for
      the token (``"noun"`` / ``"verb"``), analyses matching it are floated to the
      top. This is how the ByT5 tagger fixes ``रामः`` — it tags it a noun.
    * **Short-root demotion (fallback):** with no hint, a finite-verb reading on a
      1–2 char root is demoted below any nominal/derived reading of the same form.
      Longer roots (gam, bhū) keep verb-first, so गच्छति/जगाम are unaffected.
    """
    if not analyses:
        return analyses

    has_nominal = any(a.get("kind") in ("nominal", "derived") for a in analyses)
    wanted = {"noun": ("nominal", "derived"), "verb": ("verb",)}.get(pos_hint or "", ())

    def key(a: dict[str, Any]) -> tuple[int, int]:
        kind = a.get("kind", "unknown")
        base = kosha_engine._KIND_ORDER.get(kind, 99)
        if pos_hint:
            return (0 if kind in wanted else 1, base)
        # Fallback: demote a short-root finite verb when a nominal reading exists.
        if kind == "verb" and has_nominal:
            root = (a.get("dhatu") or {}).get("root") or ""
            if len(root) <= _SHORT_ROOT_LEN:
                return (1, base)
        return (0, base)

    return sorted(analyses, key=key)


class DhatuIdentifier:
    """Identify the dhātu behind each pada of a Sanskrit line, fully offline.

    Parameters
    ----------
    segment_fn:
        Segmentation strategy ``text_dev -> list[str] | None`` returning IAST
        members. Defaults to the sandhi-aware DP segmenter. Inject a ByT5-backed
        segmenter here to raise recall/ranking; ``None`` from it falls back to a
        plain whitespace tokenizer so identification still runs.
    pos_hint_fn:
        Optional ``iast_member -> "noun"|"verb"|None`` used to rank candidates
        (e.g. the ByT5 SLM POS tag). Optional; ranking degrades gracefully.
    """

    def __init__(
        self,
        segment_fn: Callable[[str], list[str] | None] | None = None,
        pos_hint_fn: Callable[[str], str | None] | None = None,
    ) -> None:
        self._segment = segment_fn or segmenter.segment
        self._pos_hint = pos_hint_fn

    @classmethod
    def with_byt5(cls) -> "DhatuIdentifier":
        """Build an identifier that uses ByT5 for segmentation + POS ranking.

        Falls back to the pure-rule segmenter (and no POS hint) when the ByT5
        model is unavailable, so this is always safe to call.
        """
        from sanskrit_analyzer.dhatu.byt5_ranker import ByT5Adapter

        adapter = ByT5Adapter()
        if not adapter.is_available():
            logger.info("ByT5 unavailable; using pure-rule segmenter.")
            return cls()
        return cls(segment_fn=adapter.segment, pos_hint_fn=adapter.pos_hint)

    def is_available(self) -> bool:
        return kosha_engine.is_available()

    def identify(self, text: str) -> list[TokenResult]:
        """Segment ``text`` and identify the dhātu of each resulting pada."""
        if not text or not text.strip():
            return []

        members = self._segment(text)
        if members is None:  # segmenter unavailable -> whitespace floor
            members = self._whitespace_members(text)

        results: list[TokenResult] = []
        for member_iast in members:
            dev = kosha_engine.to_devanagari(kosha_engine.slp(member_iast, "Iast"))
            if not dev:
                continue
            analysis = kosha_engine.analyze_word(dev)
            pos = self._pos_hint(member_iast) if self._pos_hint else None
            ranked = rank_analyses(analysis.get("analyses", []), pos_hint=pos)
            results.append(
                TokenResult(
                    surface=analysis.get("surface", dev),
                    slp1=analysis.get("slp1"),
                    resolved=bool(analysis.get("resolved")),
                    analyses=ranked,
                )
            )
        return results

    @staticmethod
    def _whitespace_members(text: str) -> list[str]:
        """Fallback members (IAST) when no sandhi splitter is available."""
        out: list[str] = []
        for token in kosha_engine.tokenize(text):
            iast = kosha_engine.to_iast(kosha_engine.slp(token))
            if iast:
                out.append(iast)
        return out
