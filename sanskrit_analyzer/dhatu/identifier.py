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
from sanskrit_analyzer.dhatu.resolver import get_dhatu_resolver

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


def resolve_roots(
    ranked: list[dict[str, Any]],
    slp1: str | None,
    preferred_root_fn: Callable[[str], str | None] | None = None,
) -> None:
    """Overwrite the ranked analyses' root with the resolver's reading.

    ``vidyut.kosha``'s own dhātu link is sometimes the wrong homograph
    among several (vidyā reads as vi+√dā 'give', not √vid 'know') or
    carries anubandha residue instead of the clean root (yogaḥ -> "yoji",
    not "yuj"). It is also missing entirely for many upasarga-prefixed
    nominals that the Kośa files as a plain, unlinked pratipadika
    (anuśāsana carries no dhātu link even though its bare derivative
    śāsana does). :class:`~sanskrit_analyzer.dhatu.resolver.DhatuResolver`
    fixes all three, so the top dhātu-bearing analysis here gets its root
    overwritten with the resolver's reading; when none of the ranked
    analyses carries a dhātu at all, the resolver's own (possibly peeled)
    reading is inserted as a new front-ranked analysis instead.

    ``preferred_root_fn`` is the optional ``slp1_lemma -> root_slp1|None`` hook
    consulted before the resolver settles a homograph (see
    :class:`DhatuIdentifier`).

    No-op when the vidyut data bundle is unavailable or nothing resolves,
    so callers see exactly the pre-Task-4 behaviour in that case. Shared by
    :meth:`DhatuIdentifier._resolve_roots` and the DeepRead facade so both
    public APIs agree on root resolution.
    """
    if not slp1:
        return
    resolver = get_dhatu_resolver()
    if not resolver._ensure():
        return

    lemma = next((a.get("lemma") for a in ranked if a.get("lemma")), None)
    preferred = preferred_root_fn(lemma or slp1) if preferred_root_fn else None
    candidates = [c for c in (slp1, lemma) if c]
    info = resolver.resolve(*candidates, preferred_root=preferred)
    if not info:
        return

    for a in ranked:
        dhatu = a.get("dhatu")
        if dhatu:
            dhatu["root"] = info["root_slp1"]
            dhatu["root_dev"] = kosha_engine.to_devanagari(info["root_slp1"])
            dhatu["gana_num"] = info["gana"]
            dhatu["artha_sa"] = info["artha_slp1"]
            dhatu["artha_iast"] = kosha_engine.to_iast(info["artha_slp1"])
            dhatu["english"] = kosha_engine.english_for_root(info["root_slp1"])
            dhatu["prefixes"] = info["prefixes_slp1"]
            dhatu["verified"] = info["verified"]
            break
    else:
        # No analysis carried a dhātu at all (the anuśāsana case): the
        # resolver's own reading — possibly reached by peeling a canonical
        # upasarga — is the only one available, so surface it directly.
        ranked.insert(
            0,
            {
                "kind": "derived",
                "lemma": lemma,
                "dhatu": {
                    "root": info["root_slp1"],
                    "root_dev": kosha_engine.to_devanagari(info["root_slp1"]),
                    "gana": None,
                    "gana_num": info["gana"],
                    "artha_sa": info["artha_slp1"],
                    "artha_iast": kosha_engine.to_iast(info["artha_slp1"]),
                    "english": kosha_engine.english_for_root(info["root_slp1"]),
                    "prefixes": info["prefixes_slp1"],
                    "verified": info["verified"],
                },
                "morphology": {},
            },
        )


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
    preferred_root_fn:
        Optional ``slp1_lemma -> root_slp1|None`` consulted before the
        :class:`~sanskrit_analyzer.dhatu.resolver.DhatuResolver`'s own
        heuristics settle a homographic stem (e.g. रागः could be rāj/rag/rañj).
        Meant to be backed by a dictionary's own cited etymology (MW's "fr.
        √rañj"), which this package does not carry — that lookup is the
        consuming application's concern. Optional; resolution degrades
        gracefully to the resolver's own ranking without it.

        Note the two hooks differ in what form they receive: ``pos_hint_fn``
        is called with the segmented **IAST member** (the inflected surface),
        while ``preferred_root_fn`` is called with the **SLP1 lemma**
        (falling back to the SLP1 surface when no lemma is available) — a
        dictionary's etymology is keyed by stem, not by inflected surface.
    """

    def __init__(
        self,
        segment_fn: Callable[[str], list[str] | None] | None = None,
        pos_hint_fn: Callable[[str], str | None] | None = None,
        preferred_root_fn: Callable[[str], str | None] | None = None,
    ) -> None:
        self._segment = segment_fn or segmenter.segment
        self._pos_hint = pos_hint_fn
        self._preferred_root = preferred_root_fn

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
            self._resolve_roots(ranked, analysis.get("slp1"))
            results.append(
                TokenResult(
                    surface=analysis.get("surface", dev),
                    slp1=analysis.get("slp1"),
                    resolved=bool(analysis.get("resolved")),
                    analyses=ranked,
                )
            )
        return results

    def _resolve_roots(self, ranked: list[dict[str, Any]], slp1: str | None) -> None:
        """Delegate to the module-level :func:`resolve_roots`, threading the
        instance's ``preferred_root_fn`` hook."""
        resolve_roots(ranked, slp1, self._preferred_root)

    @staticmethod
    def _whitespace_members(text: str) -> list[str]:
        """Fallback members (IAST) when no sandhi splitter is available."""
        out: list[str] = []
        for token in kosha_engine.tokenize(text):
            iast = kosha_engine.to_iast(kosha_engine.slp(token))
            if iast:
                out.append(iast)
        return out
