"""Single-pada analysis by synthesis (design doc §3.5–3.7).

For each kosha analysis of a word we re-derive the surface form through
vidyut-prakriya. A match proves the analysis, and the derivation history —
sūtra by sūtra — is the displayable proof. Non-matching analyses are dropped;
nothing is ever fabricated.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from functools import lru_cache

from sanskrit_analyzer.deep_read.kosha_engine import (
    VidyutUnavailable,
    desandhi_candidates,
    resolve_data_dir,
)
from sanskrit_analyzer.prakriya.sutra_index import get_index

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class PrakriyaStep:
    step: int
    form: str               # joined result at this step, e.g. "Bo + a + ti"
    code: str               # sūtra code, e.g. "7.3.84"
    source: str             # "ashtadhyayi", "dhatupatha", ...
    sutra_text: str | None
    kashika: str | None

    def to_dict(self) -> dict:
        return {
            "step": self.step, "form": self.form, "code": self.code,
            "source": self.source, "sutra_text": self.sutra_text,
            "kashika": self.kashika,
        }


@dataclass(frozen=True)
class PadaAnalysis:
    surface: str            # word as given (post-normalization SLP1)
    lookup_form: str        # desandhi candidate that hit the kosha
    kind: str               # "Tinanta" / "Subanta" / ...
    lemma: str
    morph: str              # human-readable feature summary from the entry
    verified: bool
    prakriya: list[PrakriyaStep] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "surface": self.surface, "lookup_form": self.lookup_form,
            "kind": self.kind, "lemma": self.lemma, "morph": self.morph,
            "verified": self.verified,
            "prakriya": [s.to_dict() for s in self.prakriya],
        }


@lru_cache(maxsize=1)
def _kosha():
    data_dir = resolve_data_dir()
    if data_dir is None:
        raise VidyutUnavailable("vidyut data bundle not found.")
    from vidyut.kosha import Kosha

    return Kosha(str(data_dir / "kosha"))


@lru_cache(maxsize=1)
def _vyakarana():
    from vidyut.prakriya import Vyakarana

    return Vyakarana()


def _entry_kind(entry) -> str:
    # PyPadaEntry_Tinanta -> "Tinanta"
    return type(entry).__name__.rsplit("_", 1)[-1]


def _entry_morph(entry) -> str:
    """Compact feature summary, e.g. "la~w kartari praTama eka" / "puM praTamA eka"."""
    if getattr(entry, "is_avyaya", False):
        return "avyaya"
    parts = [
        getattr(entry, name, None)
        for name in ("lakara", "prayoga", "purusha", "linga", "vibhakti", "vacana")
    ]
    return " ".join(str(p) for p in parts if p is not None)


# Finite-verb readings first, then nominals (plain stems before kṛdanta
# re-derivations): deterministic display order until the Phase-3 statistical
# disambiguator ranks by context.
_KIND_PRIORITY = {"Tinanta": 0, "Subanta": 1}


def _rank(entry) -> tuple[int, int]:
    kind_rank = _KIND_PRIORITY.get(_entry_kind(entry), 2)
    stem = getattr(entry, "pratipadika_entry", None)
    stem_rank = 0 if stem is None or type(stem).__name__.endswith("Basic") else 1
    return (kind_rank, stem_rank)


def _trace(prakriya) -> list[PrakriyaStep]:
    idx = get_index()
    steps: list[PrakriyaStep] = []
    for i, s in enumerate(prakriya.history, start=1):
        sutra = idx.lookup(s.code)
        steps.append(
            PrakriyaStep(
                step=i,
                form=" + ".join(str(t) for t in s.result),
                code=s.code,
                source=str(s.source),
                sutra_text=sutra.text if sutra else None,
                kashika=sutra.kashika if sutra else None,
            )
        )
    return steps


def analyze_pada(word_slp1: str, limit: int = 5) -> list[PadaAnalysis]:
    """Return verified analyses (with rule traces) for one SLP1 word."""
    word = (word_slp1 or "").strip().lstrip("'")
    if not word:
        return []
    kosha, vyakarana = _kosha(), _vyakarana()
    ranked: list[tuple[tuple[int, int], int, PadaAnalysis]] = []
    seen: set[tuple[str, str, str]] = set()
    for candidate in desandhi_candidates(word):
        for entry in kosha.get(candidate):
            kind, lemma = _entry_kind(entry), entry.lemma or ""
            morph = _entry_morph(entry)
            key = (kind, lemma, morph)
            if key in seen:
                continue
            try:
                prakriyas = vyakarana.derive(entry.to_prakriya_args())
            except Exception as exc:  # entry types derive() can't take yet
                logger.debug("derive failed for %s (%s): %s", candidate, kind, exc)
                continue
            # The kosha keys pre-visarga forms (rAmas) while derive() emits the
            # pausal surface (rAmaH); either counts as reproducing the word.
            match = next(
                (p for p in prakriyas if p.text in (candidate, word)), None
            )
            if match is None:
                continue  # analysis did not verify — drop, never fabricate
            seen.add(key)
            ranked.append(
                (
                    _rank(entry),
                    len(ranked),  # stable tiebreak: preserve kosha order
                    PadaAnalysis(
                        surface=word, lookup_form=candidate, kind=kind,
                        lemma=lemma, morph=morph, verified=True,
                        prakriya=_trace(match),
                    ),
                )
            )
    ranked.sort(key=lambda item: item[:2])
    return [a for _, _, a in ranked[:limit]]
