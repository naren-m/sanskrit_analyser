"""Kosha dhātu engine for the Deep Read facility.

This module wraps ``vidyut.kosha`` (dictionary / pada lookup) and
``vidyut.lipi`` (transliteration) to turn a single Sanskrit word into its
authentic Paninian analysis, including the dhatu (verbal root).

Why ``vidyut.kosha`` directly instead of the high-level :class:`Analyzer`?
For a *deep read* of running verse text, the ``Analyzer`` pipeline can return
the whole line unsplit with ``dhatu=None``, whereas ``vidyut.kosha`` resolves
real roots per pada (e.g. गच्छति -> √gam, Bhvadi, present 3sg). The
orchestration in :mod:`sanskrit_analyzer.deep_read.facade` keeps both paths and
falls back to this engine.

Named ``kosha_engine`` (not ``vidyut_engine``) to avoid colliding with the
engine in :mod:`sanskrit_analyzer.engines.vidyut_engine`: different
responsibility (per-word kosha lookup vs. segmentation), different name.

The module has **no web-framework imports** so it can be unit-tested in
isolation. It is the shared, scripture-agnostic core promoted out of ramayanam
(see that project's ``docs/superpowers/specs/2026-06-19-deep-read-upstream-promotion-design.md``).
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Any

# The bundle locator, the shared Kosha and the desandhi helper now live in
# ``sanskrit_analyzer.vidyut_data`` / ``utils.desandhi``. The redundant
# ``x as x`` aliases mark the ones this module does not itself call as
# deliberate re-exports: downstream callers (ramayanam) import them from here.
from sanskrit_analyzer.deep_read.closed_class import PARTICLES, PROPER_NOUNS
from sanskrit_analyzer.dhatu.resolver import DhatuResolver
from sanskrit_analyzer.utils.desandhi import desandhi_candidates
from sanskrit_analyzer.utils.desandhi import visarga_candidates as visarga_candidates
from sanskrit_analyzer.utils.normalize import clean_devanagari
from sanskrit_analyzer.vidyut_data import VidyutUnavailable
from sanskrit_analyzer.vidyut_data import is_available as is_available
from sanskrit_analyzer.vidyut_data import kosha as _kosha
from sanskrit_analyzer.vidyut_data import resolve_data_dir as resolve_data_dir

logger = logging.getLogger(__name__)

# Devanagari danda / double-danda and common verse punctuation we tokenize on.
# ASCII ':' is included because some corpora write visarga as a colon.
_DANDAS = "।॥"  # । ॥
_TOKEN_SPLIT_RE = re.compile(rf"[\s{_DANDAS}|/.,;:!?()\[\]\"'\-—]+")
# A run of Devanagari letters/marks (excludes digits) used to trim a token.
_DEVANAGARI_RUN_RE = re.compile(r"[ऀ-ॣॐ-ॣ]+")
# A token is real only if it contains at least one Devanagari *letter*
# (independent vowel अ..औ or consonant क..ह). This drops verse-reference
# digits like the "1 1 8" produced by "।।1.1.8।।".
_HAS_DEVA_LETTER_RE = re.compile(r"[ऄ-ह]")

# gana (verb-class) name -> traditional number. vidyut emits SLP1-ish names
# such as "BvAdi", "curAdi"; we match case-insensitively.
# Salience order for presenting candidate analyses: lead with the finite verb
# (most relevant for a "deep read"), then root-derived nominals, then plain nouns.
_KIND_ORDER = {"verb": 0, "derived": 1, "nominal": 2, "indeclinable": 3, "unknown": 4}

_GANA_NUMBERS = {
    "bvadi": 1,
    "adadi": 2,
    "juhotyadi": 3,
    "divadi": 4,
    "svadi": 5,
    "tudadi": 6,
    "ruDadi": 7,
    "rudhadi": 7,
    "tanadi": 8,
    "kryadi": 9,
    "curadi": 10,
}

# Small curated English gloss map for very common roots. The authoritative
# meaning is always the Dhatupatha ``artha_sa`` (Sanskrit); English here is a
# convenience and is explicitly best-effort.
_ROOT_ENGLISH = {
    "gam": "to go",
    "BU": "to be, to become",
    "as": "to be",
    "kf": "to do, to make",
    "kI": "to do",
    "sTA": "to stand",
    "df": "to tear",
    "dF": "to hold, to bear",
    "df\\Si": "to see",
    "dfS": "to see",
    "vac": "to speak",
    "vad": "to speak",
    "han": "to kill, to strike",
    "BR": "to bear, to support",
    "Da": "to place, to hold",
    "DA": "to place, to hold",
    "gE": "to sing",
    "kUj": "to coo, to warble",
    "yA": "to go",
    "i": "to go",
    "labh": "to obtain",
    "jYA": "to know",
    "man": "to think",
    "ram": "to delight, to sport",
    "muc": "to release",
    "vid": "to know",
    "sf": "to flow, to move",
    "tap": "to heat, to perform austerity",
    "pA": "to drink / to protect",
    "BAz": "to speak",
    "vas": "to dwell",
    "Sru": "to hear",
    "smf": "to remember",
    "pracC": "to ask",
}

# Curated gloss for each canonical upasarga (SLP1, as reported in
# ``Analysis.upasargas``). Surfaced next to the bare-root gloss; never composed
# into a generated sense.
_UPASARGA_ENGLISH = {
    "pra": "forth, forward",
    "parA": "away, back",
    "apa": "away, off",
    "sam": "together, completely",
    "anu": "after, along",
    "ava": "down, away",
    "nis": "out, forth",
    "dus": "bad, difficult",
    "vi": "apart, specially",
    "A": "toward, up to",
    "ni": "down, into",
    "aDi": "over, above",
    "api": "upon, close to",
    "ati": "beyond, excessively",
    "su": "well, easily",
    "ud": "up, out",
    "aBi": "toward, against",
    "prati": "back, against, toward",
    "pari": "around, thoroughly",
    "upa": "near, toward",
}

# Shared with DhatuResolver: written prefix (incl. sandhi allomorphs) -> canonical.
_UPASARGAS = DhatuResolver._UPASARGAS
_UPASARGA_KEYS_LONGEST_FIRST = sorted(_UPASARGAS, key=len, reverse=True)
_MIN_STEM_LEN = 3


@dataclass
class DhatuView:
    """A verbal root extracted from a pada analysis."""

    root: str  # SLP1 clean text, e.g. "gam"
    root_dev: str | None = None  # Devanagari, e.g. "गम्"
    gana: str | None = None  # vidyut gana name, e.g. "BvAdi"
    gana_num: int | None = None  # 1..10
    artha_sa: str | None = None  # Dhatupatha gloss in SLP1 (authoritative)
    artha_iast: str | None = None  # same gloss, IAST (readable)
    english: str | None = None  # best-effort English (may be None)

    def to_dict(self) -> dict[str, Any]:
        return {
            "root": self.root,
            "root_dev": self.root_dev,
            "gana": self.gana,
            "gana_num": self.gana_num,
            "artha_sa": self.artha_sa,
            "artha_iast": self.artha_iast,
            "english": self.english,
        }


@dataclass
class Analysis:
    """One candidate analysis of a single pada."""

    kind: str  # verb | derived | nominal | indeclinable | unknown
    lemma: str | None = None
    dhatu: DhatuView | None = None
    morphology: dict[str, str] = field(default_factory=dict)
    krt: str | None = None  # kṛt suffix of a derived reading, e.g. "Ryat", "kvi~p"
    upasargas: list[str] = field(default_factory=list)  # canonical SLP1 prefixes peeled
    # Curated gloss of the peeled prefixes; the root gloss is in dhatu.english.
    upasarga_gloss: str | None = None
    primary: bool | None = None  # set by analyze_word; True on the lead reading
    variant: str | None = None  # non-standard form note, e.g. epic non-samprasaraNa

    def to_dict(self) -> dict[str, Any]:
        d = {
            "kind": self.kind,
            "lemma": self.lemma,
            "dhatu": self.dhatu.to_dict() if self.dhatu else None,
            "morphology": self.morphology,
        }
        if self.primary is not None:
            d["primary"] = self.primary
        if self.variant:
            d["variant"] = self.variant
        if self.krt:
            d["krt"] = self.krt
        if self.upasargas:
            d["upasargas"] = list(self.upasargas)
            d["upasarga_gloss"] = self.upasarga_gloss
        return d


# ---------------------------------------------------------------------------
# Pure helpers (no vidyut needed) -- the easily-testable core.
# ---------------------------------------------------------------------------

def tokenize(text: str) -> list[str]:
    """Split a Sanskrit line into pada tokens on whitespace/danda/punctuation.

    We do NOT attempt sandhi-aware compound splitting here: ``vidyut.cheda`` is
    unavailable in this environment, so each whitespace-delimited unit is one
    token. Tokens are trimmed to their Devanagari run.
    """
    tokens: list[str] = []
    for raw in _TOKEN_SPLIT_RE.split(clean_devanagari(text or "")):
        raw = raw.strip()
        if not raw or not _HAS_DEVA_LETTER_RE.search(raw):
            continue  # skip pure digits / punctuation / verse-ref markers
        m = _DEVANAGARI_RUN_RE.search(raw)
        token = m.group(0) if m else raw
        if token:
            tokens.append(token)
    return tokens


def gana_to_number(gana_name: str | None) -> int | None:
    if not gana_name:
        return None
    return _GANA_NUMBERS.get(gana_name.lower())


def english_for_root(root: str | None) -> str | None:
    if not root:
        return None
    return _ROOT_ENGLISH.get(root)


def upasarga_gloss(upasargas: list[str]) -> str | None:
    """Curated gloss for a prefix chain, e.g. ["pari"] -> "around, thoroughly"."""
    parts = [_UPASARGA_ENGLISH[u] for u in upasargas if u in _UPASARGA_ENGLISH]
    return " + ".join(parts) or None


# ---------------------------------------------------------------------------
# Vidyut-backed engine.
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Transliteration helpers (public API).
#
# These were previously underscore-private (``_slp`` etc.) but are part of the
# de-facto contract — downstream callers (the ramayanam controller and gold
# eval) import them directly. They are now genuinely public; the underscore
# names are kept as backward-compatible aliases (see the bottom of the module).
# ---------------------------------------------------------------------------

def slp(text: str, scheme_from: str = "Devanagari") -> str:
    """Transliterate ``text`` (default Devanagari) -> SLP1.

    ``scheme_from`` is any ``vidyut.lipi.Scheme`` attribute name; passing
    ``"Slp1"`` makes this an identity transform.
    """
    from vidyut.lipi import Scheme, transliterate

    src = getattr(Scheme, scheme_from)
    # Nukta, svaras and joiners have no SLP1 mapping (see clean_devanagari).
    return transliterate(clean_devanagari(text), src, Scheme.Slp1)


def to_iast(slp_text: str | None) -> str | None:
    """Transliterate an SLP1 string to IAST, or ``None`` on empty/failure."""
    if not slp_text:
        return None
    try:
        from vidyut.lipi import Scheme, transliterate

        return transliterate(slp_text, Scheme.Slp1, Scheme.Iast)
    except Exception:  # transliteration is non-critical enrichment
        logger.debug("SLP1->IAST failed for %r", slp_text, exc_info=True)
        return None


def to_devanagari(slp_text: str | None) -> str | None:
    """Transliterate an SLP1 string to Devanagari, or ``None`` on empty/failure."""
    if not slp_text:
        return None
    try:
        from vidyut.lipi import Scheme, transliterate

        return transliterate(slp_text, Scheme.Slp1, Scheme.Devanagari)
    except Exception:
        logger.debug("SLP1->Devanagari failed for %r", slp_text, exc_info=True)
        return None


# Backward-compatible private aliases (legacy callers import these names).
_slp = slp
_to_iast = to_iast
_to_devanagari = to_devanagari


def _dhatu_view(dhatu_entry: Any) -> DhatuView | None:
    """Build a DhatuView from a vidyut DhatuEntry, defensively."""
    if dhatu_entry is None:
        return None
    root = getattr(dhatu_entry, "clean_text", None)
    if not root:
        return None
    gana_name = None
    dhatu_obj = getattr(dhatu_entry, "dhatu", None)
    if dhatu_obj is not None:
        g = getattr(dhatu_obj, "gana", None)
        gana_name = str(g) if g is not None else None
        if gana_name and "." in gana_name:  # e.g. "Gana.Bhvadi"
            gana_name = gana_name.split(".")[-1]
    artha_sa = getattr(dhatu_entry, "artha_sa", None)
    return DhatuView(
        root=root,
        root_dev=to_devanagari(root),
        gana=gana_name,
        gana_num=gana_to_number(gana_name),
        artha_sa=artha_sa,
        artha_iast=to_iast(artha_sa),
        english=english_for_root(root),
    )


def _morphology(entry: Any) -> dict[str, str]:
    morph: dict[str, str] = {}
    for field_name in ("linga", "vibhakti", "vacana", "purusha", "lakara", "prayoga"):
        val = getattr(entry, field_name, None)
        if val is None:
            continue
        s = str(val)
        if "." in s:  # enum repr -> short value
            s = s.split(".")[-1]
        morph[field_name] = s
    return morph


def _classify(entry: Any) -> Analysis:
    """Turn one vidyut PadaEntry into an Analysis with kind/lemma/dhatu/morph."""
    lemma = getattr(entry, "lemma", None)
    dhatu_entry = getattr(entry, "dhatu_entry", None)  # Tinanta -> finite verb
    prati = getattr(entry, "pratipadika_entry", None)  # Subanta -> nominal
    krdanta_dhatu = getattr(prati, "dhatu_entry", None) if prati is not None else None

    if prati is None and dhatu_entry is not None:
        kind = "verb"
        dhatu = _dhatu_view(dhatu_entry)
    elif krdanta_dhatu is not None:
        kind = "derived"  # nominal derived from a root (e.g. participle)
        dhatu = _dhatu_view(krdanta_dhatu)
        krt = getattr(prati, "krt", None)
        return Analysis(kind=kind, lemma=lemma, dhatu=dhatu,
                        morphology=_morphology(entry),
                        krt=str(krt) if krt is not None else None)
    elif getattr(entry, "is_avyaya", False):
        kind = "indeclinable"
        dhatu = None
    elif prati is not None:
        kind = "nominal"
        dhatu = None
    else:
        kind = "unknown"
        dhatu = None

    return Analysis(kind=kind, lemma=lemma, dhatu=dhatu, morphology=_morphology(entry))


def _peel_upasargas(kosha: Any, slp: str, prefixes: tuple[str, ...] = ()) -> list[Analysis]:
    """Resolve ``slp`` as upasarga(s) + a verb/derived form that has a dhatu.

    Longest written prefix first; recurses for stacked prefixes. Readings
    without a dhatu are rejected: a wrong root is worse than UNKNOWN.
    """
    for written in _UPASARGA_KEYS_LONGEST_FIRST:
        if not slp.startswith(written) or len(slp) - len(written) < _MIN_STEM_LEN:
            continue
        chain = prefixes + (_UPASARGAS[written],)
        rest = slp[len(written):]
        found: list[Analysis] = []
        seen: set[tuple] = set()
        for cand in desandhi_candidates(rest):
            for entry in kosha.get(cand):
                a = _classify(entry)
                if a.kind not in ("verb", "derived") or a.dhatu is None:
                    continue
                key = (a.kind, a.lemma, a.dhatu.root, tuple(sorted(a.morphology.items())))
                if key in seen:
                    continue
                seen.add(key)
                a.upasargas = list(chain)
                a.upasarga_gloss = upasarga_gloss(a.upasargas)
                found.append(a)
        if found:
            return found
        found = _peel_upasargas(kosha, rest, chain)
        if found:
            return found
    return []


# Irregular consonant stems whose bare stem and some inflected forms the kosha
# does not index (e.g. पथिन् itself, पथः). Each stem is (SLP1 stem, linga).
_IRREGULAR_STEMS = (("paTin", "Pum"), ("ahan", "Napumsaka"), ("Svan", "Pum"))


@lru_cache(maxsize=1)
def _irregular_forms() -> dict[str, tuple[Analysis, ...]]:
    """Cached wrapper: a vidyut.prakriya failure is cached as an empty table."""
    try:
        return _build_irregular_forms()
    except Exception as exc:
        logger.warning("irregular-stem derivation failed: %s", exc)
        return {}


def _build_irregular_forms() -> dict[str, tuple[Analysis, ...]]:
    """surface (SLP1) -> nominal analyses, derived by vidyut.prakriya.

    Every entry is generated by the Paninian engine, so a form only appears
    here if the derivation confirms it. The bare stem is included too: it is
    what a dictionary headword or a compound's first member looks like.
    """
    from vidyut.prakriya import Linga, Pada, Pratipadika, Vacana, Vibhakti, Vyakarana

    engine = Vyakarana()
    forms: dict[str, list[Analysis]] = {}
    for stem, linga_name in _IRREGULAR_STEMS:
        linga = getattr(Linga, linga_name)
        forms.setdefault(stem, []).append(
            Analysis(kind="nominal", lemma=stem, morphology={"linga": str(linga)}))
        for vibhakti in Vibhakti.choices():
            for vacana in Vacana.choices():
                for d in engine.derive(Pada.Subanta(
                        pratipadika=Pratipadika.basic(stem), linga=linga,
                        vibhakti=vibhakti, vacana=vacana)):
                    forms.setdefault(d.text, []).append(Analysis(
                        kind="nominal", lemma=stem,
                        morphology={"linga": str(linga), "vibhakti": str(vibhakti),
                                    "vacana": str(vacana)}))
    return {k: tuple(v) for k, v in forms.items()}


def _irregular_analyses(candidates: list[str]) -> list[Analysis]:
    forms = _irregular_forms()
    return [a for c in candidates for a in forms.get(c, ())]


def _analysis_key(a: Analysis) -> tuple:
    return (a.kind, a.lemma, a.dhatu.root if a.dhatu else None,
            tuple(sorted(a.morphology.items())))


# Surface forms whose kosha readings lack, or do not lead with, the dictionary
# stem: the bare stem maha/mahA is the first member of compounds and the
# standalone adjective 'great' (lemma mahat), but the kosha only offers root
# mahi/mah readings; paTi is the locative of paTin, not of the derived paT.
_STEM_LEMMAS = {"maha": "mahat", "mahA": "mahat", "paTi": "paTin"}

# Epic (non-samprasaraNa) presents of pracC: surface -> its standard form,
# whose kosha reading supplies the root and morphology.
_EPIC_PRESENTS = {"pracCati": "pfcCati"}


def _epic_analyses(kosha: Any, slp: str) -> list[Analysis]:
    standard = _EPIC_PRESENTS.get(slp)
    if standard is None:
        return []
    found = []
    for entry in kosha.get(standard):
        a = _classify(entry)
        if a.kind == "verb" and a.dhatu is not None:
            a.variant = f"non-samprasAraNa form of {standard}"
            found.append(a)
    return found


def _rank(analyses: list[Analysis]) -> list[Analysis]:
    """Order by ``_KIND_ORDER``.

    The sort is stable, so ties keep the kosha's lookup order (itself
    deterministic: desandhi candidates in order, entries in kosha order).
    A lemma-agreement vote key was tried and dropped: it lowered lemma
    accuracy on the in-repo gold, so agreement ranking is still open.
    """
    return sorted(analyses, key=lambda a: _KIND_ORDER.get(a.kind, 99))


def _gate_and_rank(analyses: list[Analysis], slp: str,
                   candidates: list[str]) -> list[Analysis]:
    """Drop spurious readings of closed-class words and names, then order.

    Particles keep only their indeclinable reading; epic proper nouns lose
    their verb readings and lead with the nominal; maha/mahA lead with the
    nominal ``mahat``. Everything else is ordered by :func:`_rank`.
    """
    if slp in PARTICLES:
        kept = [a for a in analyses if a.kind == "indeclinable"]
        return kept or [Analysis(kind="indeclinable", lemma=slp)]
    if slp in _STEM_LEMMAS:
        stem = _STEM_LEMMAS[slp]

        def is_lead(a: Analysis) -> bool:
            return a.kind == "nominal" and a.lemma == stem

        lead = [a for a in analyses if is_lead(a)] or [Analysis(kind="nominal", lemma=stem)]
        return lead + _rank([a for a in analyses if not is_lead(a)])
    name = next((a.lemma for a in analyses if a.lemma in PROPER_NOUNS), None) \
        or next((c for c in candidates if c in PROPER_NOUNS), None)
    if name is None:
        return _rank(analyses)
    kept = [a for a in analyses if a.kind != "verb"]
    if not any(a.kind == "nominal" for a in kept):
        kept.append(Analysis(kind="nominal", lemma=name))
    return sorted(kept, key=lambda a: -1 if a.kind == "nominal" else _KIND_ORDER.get(a.kind, 99))


def _mark_primary(analyses: list[Analysis]) -> list[dict[str, Any]]:
    """Serialize, flagging the first (lead) reading as primary."""
    for i, a in enumerate(analyses):
        a.primary = i == 0
    return [a.to_dict() for a in analyses]


def analyze_word(devanagari: str) -> dict[str, Any]:
    """Analyze a single Devanagari pada -> {surface, slp1, resolved, analyses}.

    Never raises for a single bad token: failures degrade to an ``unknown``
    analysis carrying the reason.
    """
    surface = devanagari
    try:
        slp = _slp(devanagari)
    except Exception as exc:  # transliteration failed -> cannot look up
        logger.warning("transliteration failed for %r: %s", devanagari, exc)
        return {
            "surface": surface,
            "slp1": None,
            "resolved": False,
            "analyses": _mark_primary([Analysis(kind="unknown")]),
            "error": f"transliteration failed: {exc}",
        }

    analyses: list[Analysis] = []
    seen: set[tuple] = set()
    candidates: list[str] = []
    try:
        candidates = desandhi_candidates(slp)
        kosha = _kosha()
        for cand in candidates:
            for entry in kosha.get(cand):
                a = _classify(entry)
                key = _analysis_key(a)
                if key in seen:
                    continue
                seen.add(key)
                analyses.append(a)
        if not analyses:  # only for words the kosha misses, so hits never change
            for a in _irregular_analyses(candidates):
                key = _analysis_key(a)
                if key not in seen:
                    seen.add(key)
                    analyses.append(a)
        if not analyses:
            analyses = _epic_analyses(kosha, slp)
        if not analyses:
            analyses = _peel_upasargas(kosha, slp)
    except VidyutUnavailable:
        raise
    except Exception as exc:  # one bad word should not kill the request
        logger.warning("kosha lookup failed for %r (slp=%s): %s", surface, slp, exc)
        return {
            "surface": surface,
            "slp1": slp,
            "resolved": False,
            "analyses": _mark_primary([Analysis(kind="unknown")]),
            "error": str(exc),
        }

    resolved = bool(analyses)
    if not resolved:
        analyses = [Analysis(kind="unknown")]
    # Lead with the most salient reading (finite verb first) unless gated.
    analyses = _gate_and_rank(analyses, slp, candidates)
    out = {
        "surface": surface,
        "slp1": slp,
        "resolved": resolved,
        "analyses": _mark_primary(analyses),
    }
    if not resolved:
        out["reason"] = _unresolved_reason(slp)
    return out


def _unresolved_reason(slp: str) -> str:
    """Best-effort explanation for why a token did not resolve.

    Long unresolved tokens in connected verse text are almost always compounds
    (samāsa) or two padas glued by sandhi/orthography — which we cannot split
    until a full vidyut segmenter (cheda) data bundle is available.
    """
    if len(slp) >= 11:
        return ("likely a compound (samāsa) or sandhi-joined padas; word "
                "segmentation is not yet available (needs vidyut cheda data)")
    return "form not found in the kosha (lexicon)"
