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
ensemble member in :mod:`sanskrit_analyzer.engines.vidyut_engine`: different
responsibility (per-word kosha lookup vs. segmentation), different name.

The module has **no web-framework imports** so it can be unit-tested in
isolation. It is the shared, scripture-agnostic core promoted out of ramayanam
(see that project's ``docs/superpowers/specs/2026-06-19-deep-read-upstream-promotion-design.md``).
"""

from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any

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
}


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

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "lemma": self.lemma,
            "dhatu": self.dhatu.to_dict() if self.dhatu else None,
            "morphology": self.morphology,
        }


class VidyutUnavailable(RuntimeError):
    """Raised when the vidyut data bundle cannot be located/loaded."""


def resolve_data_dir() -> Path | None:
    """Find a vidyut data directory that actually contains a ``kosha`` subdir.

    Order: ``VIDYUT_DATA_DIR`` env, a ``vidyut-0.4.0/`` bundle in the current
    working directory (a consuming project run from its repo root — e.g.
    ramayanam's ``python run.py`` — ships the bundle there), then the
    user-level ``~/.vidyut-data``. The bundle path is *data*, not a secret, so a
    default search is fine.

    This is deliberately layout-agnostic: as a shared library module we cannot
    assume any fixed depth relative to a host repo, so discovery is driven by an
    explicit env var and well-known locations rather than ``__file__`` arithmetic.
    """
    candidates: list[Path] = []
    env = os.environ.get("VIDYUT_DATA_DIR")
    if env:
        candidates.append(Path(env).expanduser())
    candidates.append(Path.cwd() / "vidyut-0.4.0")
    candidates.append(Path.home() / ".vidyut-data")

    for c in candidates:
        if (c / "kosha").is_dir():
            return c
    return None


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
    for raw in _TOKEN_SPLIT_RE.split(text or ""):
        raw = raw.strip()
        if not raw or not _HAS_DEVA_LETTER_RE.search(raw):
            continue  # skip pure digits / punctuation / verse-ref markers
        m = _DEVANAGARI_RUN_RE.search(raw)
        token = m.group(0) if m else raw
        if token:
            tokens.append(token)
    return tokens


def desandhi_candidates(slp: str) -> list[str]:
    """Generate lookup candidates for a SLP1 form, undoing common final sandhi.

    Two facts force this. (1) Kosha is keyed by the underlying ``-s``/``-r``/stem
    form, not the pausal visarga ``-H``. (2) In *running* verse text a word-final
    visarga has already mutated by sandhi — ``-aḥ`` → ``-o`` before a voiced
    sound (रामः → रामो), visarga → ``ś``/``ṣ`` before sibilants, final ``m`` →
    anusvāra ``ṃ``. Without reversing these, almost nothing in connected text
    resolves. Order is preserved and de-duplicated.
    """
    out = [slp]
    if slp:
        stem, last = slp[:-1], slp[-1]
        if last == "H":  # visarga (pausa) -> -as / -ar
            out += [stem + "s", stem + "r"]
        elif last == "o":  # -aḥ / -as -> -o before voiced (रामो, महावीर्यो)
            out += [stem + "as", stem + "aH", stem + "a"]
        elif last in ("S", "z"):  # visarga -> ś / ṣ before c-/ṭ-
            out += [stem + "H", stem + "s"]
        elif last == "M":  # final m -> anusvāra ṃ
            out += [stem + "m"]
    seen: set[str] = set()
    uniq: list[str] = []
    for c in out:
        if c and c not in seen:
            seen.add(c)
            uniq.append(c)
    return uniq


# Backwards-compatible alias (the function used to only handle visarga).
visarga_candidates = desandhi_candidates


def gana_to_number(gana_name: str | None) -> int | None:
    if not gana_name:
        return None
    return _GANA_NUMBERS.get(gana_name.lower())


def english_for_root(root: str | None) -> str | None:
    if not root:
        return None
    return _ROOT_ENGLISH.get(root)


# ---------------------------------------------------------------------------
# Vidyut-backed engine.
# ---------------------------------------------------------------------------

@lru_cache(maxsize=1)
def _kosha():
    data_dir = resolve_data_dir()
    if data_dir is None:
        raise VidyutUnavailable(
            "vidyut data bundle not found. Checked VIDYUT_DATA_DIR, "
            "<repo>/vidyut-0.4.0, and ~/.vidyut-data."
        )
    from vidyut.kosha import Kosha  # imported lazily so import-time stays cheap

    logger.info("Loading vidyut kosha from %s", data_dir / "kosha")
    return Kosha(str(data_dir / "kosha"))


def is_available() -> bool:
    """True if the vidyut data bundle is present (does not load the kosha)."""
    return resolve_data_dir() is not None


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
    return transliterate(text, src, Scheme.Slp1)


def to_iast(slp_text: str | None) -> str | None:
    """Transliterate an SLP1 string to IAST, or ``None`` on empty/failure."""
    if not slp_text:
        return None
    try:
        from vidyut.lipi import Scheme, transliterate

        return transliterate(slp_text, Scheme.Slp1, Scheme.Iast)
    except Exception:  # transliteration is non-critical enrichment
        return None


def to_devanagari(slp_text: str | None) -> str | None:
    """Transliterate an SLP1 string to Devanagari, or ``None`` on empty/failure."""
    if not slp_text:
        return None
    try:
        from vidyut.lipi import Scheme, transliterate

        return transliterate(slp_text, Scheme.Slp1, Scheme.Devanagari)
    except Exception:
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
            "analyses": [Analysis(kind="unknown").to_dict()],
            "error": f"transliteration failed: {exc}",
        }

    analyses: list[Analysis] = []
    seen: set[tuple] = set()
    try:
        kosha = _kosha()
        for cand in desandhi_candidates(slp):
            for entry in kosha.get(cand):
                a = _classify(entry)
                key = (a.kind, a.lemma, a.dhatu.root if a.dhatu else None,
                       tuple(sorted(a.morphology.items())))
                if key in seen:
                    continue
                seen.add(key)
                analyses.append(a)
    except VidyutUnavailable:
        raise
    except Exception as exc:  # one bad word should not kill the request
        logger.warning("kosha lookup failed for %r (slp=%s): %s", surface, slp, exc)
        return {
            "surface": surface,
            "slp1": slp,
            "resolved": False,
            "analyses": [Analysis(kind="unknown").to_dict()],
            "error": str(exc),
        }

    resolved = bool(analyses)
    if not resolved:
        analyses = [Analysis(kind="unknown")]
    # Stable sort: lead with the most salient reading (finite verb first).
    analyses.sort(key=lambda a: _KIND_ORDER.get(a.kind, 99))
    out = {
        "surface": surface,
        "slp1": slp,
        "resolved": resolved,
        "analyses": [a.to_dict() for a in analyses],
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
