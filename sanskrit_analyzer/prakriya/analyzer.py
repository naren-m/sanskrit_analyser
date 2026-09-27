"""Single-pada analysis by synthesis (design doc §3.5–3.7).

For each kosha analysis of a word we re-derive the surface form through
vidyut-prakriya. A match proves the analysis, and the derivation history —
sūtra by sūtra — is the displayable proof. Non-matching analyses are dropped;
nothing is ever fabricated.
"""
from __future__ import annotations

import logging
import re
from collections import Counter
from dataclasses import dataclass, field
from functools import lru_cache

from sanskrit_analyzer.prakriya.sutra_index import get_index
from sanskrit_analyzer.utils.desandhi import desandhi_candidates
from sanskrit_analyzer.vidyut_data import kosha as _kosha

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


# Adhyāyas 3–5 sit under the "pratyayaḥ" adhikāra (3.1.1), so a term those
# sūtras add is a pratyaya. Only Aṣṭādhyāyī codes (a.p.n) qualify.
_PRATYAYA_SUTRA = re.compile(r"[345]\.\d+\.\d+")
# Augments (āgama) of the liṅ/tiṅ that 3.4.102-3.4.107 insert as their own
# terms; they sit inside adhyāya 3 but are not pratyayas.
_AGAMAS = {"sIyu~w", "yAsu~w", "su~w"}


def pratyayas(steps: list[PrakriyaStep]) -> list[dict]:
    """The pratyayas a derivation introduces, in order, with the sūtra for each.

    Read off the trace, not guessed: a pratyaya is a term inserted by a sūtra
    in adhyāyas 3–5, or the substitute a 3.4.77 ("lasya") sūtra puts in place
    of a lakāra once its it-markers are gone (``l`` -> ``tip``). Later edits to
    a pratyaya (3.4.79 ``ta`` -> ``te``) are not new pratyayas and are skipped.
    """
    found: list[dict] = []
    prev: list[str] = []
    for step in steps:
        terms = step.form.split(" + ")
        if _PRATYAYA_SUTRA.fullmatch(step.code):
            now, before = Counter(terms), Counter(prev)
            # vidyut sometimes carries an empty placeholder term; ignore it.
            added = [t for t in now - before if t and t not in _AGAMAS]
            grew = len(terms) > len(prev)
            # A lakāra after it-removal is "l" (la~w) or "la" (laN).
            replaced_lakara = any(t.startswith("l") for t in before - now)
            if len(added) == 1 and (grew or replaced_lakara):
                found.append(
                    {"pratyaya": added[0], "sutra": step.code, "sutra_text": step.sutra_text}
                )
        prev = terms
    return found


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
            # pausal surface (rAmaH); either counts as reproducing the word. The
            # pausal form of the candidate counts too, or a sandhi-mutated
            # surface (rAmo -> rAmas) could never verify against rAmaH.
            accepted = {candidate, word, re.sub(r"[sr]$", "H", candidate)}
            match = next((p for p in prakriyas if p.text in accepted), None)
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
