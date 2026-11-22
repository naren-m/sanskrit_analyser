"""Verify one word: hypothesis -> vidyut derivation -> surface match.

A reading is *verified* only when vidyut-prakriya regenerates the observed
surface. Its derivation history is the proof and the sūtra trace shown to the
user. Order of attempts:

1. Generate-and-match from the ByT5 hypothesis (lemma + decoded tags):
   tiṅanta with upasarga stripping, subanta with pronoun lemma mapping.
2. Two reader rules vidyut does not model, applied on top of a vidyut
   derivation and labelled ``source="vidyut+reader-rule"``:
   enclitic te/me/vām/nau/vaḥ/naḥ (8.1.20-22) and no aṭ augment after mā
   (6.4.74).
3. Kosha candidates (``prakriya.analyze_pada``) ranked by agreement with the
   hypothesis tags.
4. Nothing verified: the model's reading, ``verified=False``.

No sūtra number here ever comes from a model.
"""
from __future__ import annotations

import csv
import logging
import re
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any

from sanskrit_analyzer.prakriya.analyzer import PrakriyaStep, _trace, analyze_pada
from sanskrit_analyzer.reader.tags import Morph

logger = logging.getLogger(__name__)

_GLOSS_CSV = Path(__file__).resolve().parents[1] / "data" / "dhatu-gloss-en.csv"

UPASARGAS = ("pra", "parA", "apa", "sam", "anu", "ava", "nis", "dus", "vi", "A", "ni", "aDi",
             "api", "ati", "su", "ud", "aBi", "prati", "pari", "upa")
# Gati words that vidyut also takes as prefixes (puraskaroti, Avizkaroti).
GATI = ("puras", "Avis", "prAdus", "tiras", "sat", "alam", "antar")
# Consonant-final prefixes as they surface before the root.
_PREFIX_SURFACES = {
    "sam": ("sam", "saM", "saY", "saN", "san"), "ud": ("ud", "ut", "uc", "uj", "ul", "un", "ug"),
    "nis": ("nis", "nir", "niz", "niS", "niH"), "dus": ("dus", "dur", "duz", "duS", "duH"),
    "puras": ("puras", "puraH", "puraS", "puraz"), "Avis": ("Avis", "Aviz", "AviH", "Avir"),
    "prAdus": ("prAdus", "prAdur", "prAduz"), "tiras": ("tiras", "tiraH", "tiraz"),
    "sat": ("sat", "sad"), "antar": ("antar", "antaH"),
}
# Suppletive present stems ByT5 gives as lemmas (7.3.78 pAGrA... dfS -> paSya).
SUPPLETIVE = {"paS": "dfS"}
# ByT5 names the 1st/2nd-person pronouns by their bound stems.
PRONOUN_LEMMA = {"tvad": "yuzmad", "mad": "asmad", "ka": "kim", "yuSmad": "yuzmad"}

_LAKARA_ATTR = {"law": "Lat", "laN": "Lan", "liw": "Lit", "luN": "Lun", "lfw": "Lrt",
                "luw": "Lut", "low": "Lot", "viDiliN": "VidhiLin", "ASIrliN": "AshirLin"}
_VIBHAKTI_ATTR = {"praTamA": "Prathama", "dvitIyA": "Dvitiya", "tftIyA": "Trtiya",
                  "caturTI": "Caturthi", "paYcamI": "Panchami", "zazWI": "Sasthi",
                  "saptamI": "Saptami", "samboDanam": "Sambodhana"}
_LINGA_ATTR = {"puM": "Pum", "strI": "Stri", "napuMsaka": "Napumsaka"}
_VACANA_ATTR = {"eka": "Eka", "dvi": "Dvi", "bahu": "Bahu"}
_PURUSHA_ATTR = {"praTama": "Prathama", "maDyama": "Madhyama", "uttama": "Uttama"}

# Enclitic substitutes for yuṣmad/asmad (8.1.20-22). Key: (vibhakti, vacana).
_ENCLITIC = {
    ("zazWI", "eka"): ({"yuzmad": "te", "asmad": "me"}, "8.1.22"),
    ("caturTI", "eka"): ({"yuzmad": "te", "asmad": "me"}, "8.1.22"),
    ("dvitIyA", "eka"): ({"yuzmad": "tvA", "asmad": "mA"}, "8.1.23"),
    ("zazWI", "dvi"): ({"yuzmad": "vAm", "asmad": "nO"}, "8.1.20"),
    ("caturTI", "dvi"): ({"yuzmad": "vAm", "asmad": "nO"}, "8.1.20"),
    ("dvitIyA", "dvi"): ({"yuzmad": "vAm", "asmad": "nO"}, "8.1.20"),
    ("zazWI", "bahu"): ({"yuzmad": "vas", "asmad": "nas"}, "8.1.21"),
    ("caturTI", "bahu"): ({"yuzmad": "vas", "asmad": "nas"}, "8.1.21"),
    ("dvitIyA", "bahu"): ({"yuzmad": "vas", "asmad": "nas"}, "8.1.21"),
}


@dataclass
class Reading:
    surface: str                      # SLP1
    lemma: str
    kind: str                         # tinanta | subanta | avyaya | compound_member | unknown
    features: dict[str, str] = field(default_factory=dict)
    verified: bool = False
    source: str = "model"             # vidyut | vidyut+reader-rule | kosha | model
    dhatu: dict[str, Any] | None = None
    trace: list[PrakriyaStep] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    alternatives: list[dict[str, str]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "surface": self.surface, "lemma": self.lemma, "kind": self.kind,
            "features": self.features, "verified": self.verified, "source": self.source,
            "dhatu": self.dhatu, "notes": self.notes, "alternatives": self.alternatives,
            "trace": [s.to_dict() for s in self.trace],
        }


def same_surface(a: str, b: str) -> bool:
    """Equal up to pausa spelling and ṇatva.

    Final s/r vs visarga, anusvāra vs m, and R vs n: a compound head can take
    ṇ from an r/ṣ in an earlier member (8.4.2, varza-BogyeRa vs Bogyena).
    """
    def fold(s: str) -> str:
        return re.sub(r"[sr]$", "H", s.replace("M", "m")).replace("R", "n")
    return bool(a) and fold(a) == fold(b)


@lru_cache(maxsize=1)
def _vyakarana():
    from vidyut.prakriya import Vyakarana
    return Vyakarana()


@lru_cache(maxsize=1)
def _gloss_en() -> dict[str, tuple[str, str]]:
    if not _GLOSS_CSV.exists():
        return {}
    with _GLOSS_CSV.open(encoding="utf-8") as fh:
        return {r["code"]: (r["gloss_en"], r.get("source") or "") for r in csv.DictReader(fh)}


_NASAL_FOR = {**dict.fromkeys("kKgG", "N"), **dict.fromkeys("cCjJ", "Y"),
              **dict.fromkeys("wWqQ", "R"), **dict.fromkeys("tTdD", "n"),
              **dict.fromkeys("pPbB", "m")}


def citation_root(upadesa: str) -> str:
    """Dhātupāṭha upadeśa -> the citation root a learner knows (Buj, nI, kamp, sTA)."""
    from sanskrit_analyzer.dhatu.dhatupatha import strip_anubandhas

    raw = upadesa.replace("\\", "").replace("^", "")
    idit = bool(re.search(r"i~$", raw))
    root = re.sub(r"i~$", "", strip_anubandhas(upadesa))   # df\Si~r -> dfSi~ -> dfS
    if root.startswith("R"):                       # 6.1.65 Ro naH
        root = "n" + root[1:]
    if root.startswith("z"):                       # 6.1.64, with the dental restored
        root = "s" + root[1:].replace("W", "T", 1).replace("w", "t", 1)
    if idit and root and root[-1] in _NASAL_FOR:   # 7.1.58 idito num DAtoH
        root = root[:-1] + _NASAL_FOR[root[-1]] + root[-1]
    if re.search(r"[aiufx]C$", root):              # 6.1.73 che ca
        root = root[:-1] + "cC"
    return root


def dhatu_info(code: str, entry: dict[str, Any] | None = None) -> dict[str, Any]:
    gloss, source = _gloss_en().get(code, (None, ""))
    info: dict[str, Any] = {"code": code, "gloss_en": gloss,
                            "gloss_source": "llm" if source == "ollama" else source or None}
    if entry:
        info.update(root=citation_root(entry.get("dhatu_slp1") or ""),
                    upadesa=entry.get("dhatu_slp1"), artha=entry.get("artha_slp1"),
                    gana=entry.get("gana"))
    return info


def _strip_one(rest: str):
    """Yield (prefix, remainder) for one prefix at the start of ``rest``.

    Handles the vowel sandhi at the junction: upa+A -> upA, ati+A -> atyA,
    pra+Ikz -> prekz, vi+Ikz -> vIkz, anu+A -> anvA.
    """
    for u in UPASARGAS + GATI:
        for form in _PREFIX_SURFACES.get(u, (u,)):
            if rest.startswith(form) and len(rest) > len(form) + 1:
                yield u, rest[len(form):]
        head, last = u[:-1], u[-1]
        after = len(head) + 1  # index just past the merged junction letter
        if last in "aA":
            for merged, starts in (("A", "aA"), ("e", "iI"), ("o", "uU"), ("E", "eE"),
                                   ("O", "oO"), ("ar", "f")):
                if rest.startswith(head + merged):
                    for v in starts:
                        yield u, v + rest[len(head + merged):]
        elif last == "i":
            if rest.startswith(head + "I"):
                yield u, "i" + rest[after:]
                yield u, "I" + rest[after:]
            if rest.startswith(head + "y") and len(rest) > after and rest[after] in "aAuUeEoOf":
                yield u, rest[after:]
        elif last == "u":
            if rest.startswith(head + "U"):
                yield u, "u" + rest[after:]
            if rest.startswith(head + "v") and len(rest) > after and rest[after] in "aAiIeEoOf":
                yield u, rest[after:]


def _root_splits(lemma: str) -> list[tuple[list[str], str]]:
    """(prefixes, root) splits of a verbal lemma, up to three prefixes deep."""
    out: list[tuple[list[str], str]] = [([], SUPPLETIVE.get(lemma, lemma))]
    frontier = [([], lemma)]
    while frontier:
        prefixes, rest = frontier.pop()
        for u, remainder in _strip_one(rest):
            if prefixes and prefixes[-1] == u:
                continue  # A+A, pra+pra: never a real prefix chain
            cand = (prefixes + [u], SUPPLETIVE.get(remainder, remainder))
            if cand not in out:
                out.append(cand)
                if len(cand[0]) < 3:
                    frontier.append((cand[0], remainder))
    return out


# Undo the guṇa/vṛddhi a causative (ṇic) stem shows: moc-ay -> muc, pAt-ay -> pat.
_CAUSATIVE_UNDO = (("Av", "u"), ("Ay", "i"), ("ar", "f"), ("Ar", "f"), ("al", "f"), ("o", "u"),
                   ("e", "i"), ("O", "u"), ("E", "i"), ("A", "a"))


def _causative_roots(stem: str) -> list[str]:
    roots = [stem]
    for frm, to in _CAUSATIVE_UNDO:
        i = stem.rfind(frm)
        if i >= 0:
            roots.append(stem[:i] + to + stem[i + len(frm):])
    return roots


def _dhatu_candidates(lemma: str):
    """Yield (upasargas, dhātupāṭha entry, vidyut Dhatu) for a verbal lemma.

    A lemma in -ay is tried as a 10th-class root as written, and as a
    causative (ṇic) of the root with its guṇa/vṛddhi undone.
    """
    from vidyut.prakriya import Sanadi

    from sanskrit_analyzer.dhatu.conjugation import _entries_by_code
    from sanskrit_analyzer.dhatu.dhatupatha import get_dhatu_kosha

    kosha, entries = get_dhatu_kosha(), _entries_by_code()
    seen: set[tuple[str, ...]] = set()

    def emit(prefixes, root, causative):
        for e in kosha.lookup(root):
            key = (*prefixes, e["code"], str(causative))
            vid = entries.get(e["code"])
            if vid is None or key in seen:
                continue
            seen.add(key)
            yield prefixes, e, vid.dhatu.with_sanadi([Sanadi.Ric]) if causative else vid.dhatu

    for prefixes, root in _root_splits(lemma):
        yield from emit(prefixes, root, False)
    if lemma.endswith("ay"):
        for prefixes, root in _root_splits(lemma[:-2]):
            for cand in _causative_roots(root):
                yield from emit(prefixes, cand, False)
                yield from emit(prefixes, cand, True)


def _with_prefixes(prefixes: list[str], dhatu):
    return dhatu.with_prefixes(prefixes) if prefixes else dhatu


def _dhatu_feats(prefixes: list[str], dhatu) -> dict[str, str]:
    """Features every verbal derivation shares: causative sanādi and upasargas."""
    feats: dict[str, str] = {}
    if dhatu.sanadi:
        feats["sanadi"] = "Ric (causative)"
    if prefixes:
        feats["upasarga"] = "+".join(prefixes)
    return feats


def _tinanta(surface: str, lemma: str, morph: Morph, augmentless: bool) -> Reading | None:
    from vidyut.prakriya import DhatuPada, Lakara, Pada, Prayoga, Purusha, Vacana

    v = _vyakarana()
    # Active first even when tagged passive: jAyate / mriyate are active
    # ātmanepada forms that a passive derivation also produces.
    prayogas = [(Prayoga.Kartari, "kartari")]
    if morph.prayoga == "karmaRi":
        prayogas.append((Prayoga.Karmani, "karmaRi"))
    for prefixes, entry, dhatu in _dhatu_candidates(lemma):
        d = _with_prefixes(prefixes, dhatu)
        for prayoga, prayoga_name in prayogas:
            for lak in morph.lakaras:
                for pada in (DhatuPada.Parasmaipada, DhatuPada.Atmanepada):
                    try:
                        prakriyas = v.derive(Pada.Tinanta(
                            dhatu=d, prayoga=prayoga,
                            lakara=getattr(Lakara, _LAKARA_ATTR[lak]),
                            purusha=getattr(Purusha, _PURUSHA_ATTR[morph.purusha]),
                            vacana=getattr(Vacana, _VACANA_ATTR[morph.vacana]),
                            dhatu_pada=pada))
                    except Exception:  # vidyut rejects some combinations
                        logger.debug("tinanta derive failed for %s (%s, %s)",
                                     surface, lak, prayoga_name, exc_info=True)
                        continue
                    for p in prakriyas:
                        if same_surface(p.text, surface):
                            rule = None
                        elif augmentless and lak in ("luN", "laN") and p.text.startswith("a") \
                                and same_surface(p.text[1:], surface):
                            rule = "6.4.74 na mAN-yoge: no aw augment after mA (reader rule)"
                        else:
                            continue
                        feats = {"lakara": lak, "purusha": morph.purusha, "vacana": morph.vacana,
                                 "prayoga": prayoga_name, "pada": str(pada).split(".")[-1],
                                 **_dhatu_feats(prefixes, dhatu)}
                        return Reading(surface, citation_root(entry["dhatu_slp1"]), "tinanta",
                                       feats, True, "vidyut+reader-rule" if rule else "vidyut",
                                       dhatu_info(entry["code"], entry), _trace(p),
                                       [rule] if rule else [])
    return None


_PARTICIPLE_KRTS = ("kta", "ktavatu", "Satf", "SAnac", "tavya", "anIyar", "yat", "Ryat")
_PARTICLES = ("cana", "cit", "api")


def _spelling_variants(stem: str) -> set[str]:
    """Dictionary spellings of a stem: anusvāra vs class nasal, r-doubling (Darmma)."""
    out = {stem, re.sub(r"N(?=[kKgG])", "M", stem),
           re.sub(r"r([kKgGcCjJwWqQtTdDpPbBmyvlnRSzs])", r"r\1\1", stem)}
    for nasal, cls in (("N", "kKgGN"), ("Y", "cCjJY"), ("R", "wWqQR"), ("n", "tTdDn"),
                       ("m", "pPbBm")):
        out.add(re.sub(rf"M(?=[{cls}])", nasal, stem))
    return out


@lru_cache(maxsize=20000)
def stem_attested(stem: str) -> str | None:
    """Where a nominal stem is attested ("lexicon" / "kosha"), or None.

    vidyut will decline *any* string, so a basic-stem derivation proves
    nothing unless the stem itself is a known word. This is the check that
    keeps a bad split (me+ripuH read as one word "meripu") from passing as
    verified.
    """
    from sanskrit_analyzer import lexicon
    from sanskrit_analyzer.vidyut_data import kosha

    names = _spelling_variants(stem)
    if any(lexicon.lookup(v) for v in names):
        return "lexicon"
    k = kosha()
    for form in (stem, stem + "H", stem + "m", stem + "s"):
        if any((e.lemma or "") in names for e in k.get(form)):
            return "kosha"
    return None


def _basic_stems(lemma: str):
    from vidyut.prakriya import Pratipadika, Taddhita

    stem = PRONOUN_LEMMA.get(lemma, lemma)
    stem = re.sub(r"([mv])ant$", r"\1at", stem)   # hanumant -> hanumat
    yield Pratipadika.basic(stem), stem, {}, None
    if stem.endswith(("A", "I")):
        try:
            yield Pratipadika.nyap(stem), stem, {}, None
        except Exception:  # vidyut rejects some stems as nyap
            logger.debug("nyap stem rejected: %s", stem, exc_info=True)
    for suffix, taddhita in (("vat", "matup"), ("mat", "matup"), ("vat", "vatup")):
        if stem.endswith(suffix) and len(stem) > len(suffix) + 1:
            base = stem[: -len(suffix)]
            yield (Pratipadika.taddhitanta(Pratipadika.basic(base), getattr(Taddhita, taddhita)),
                   stem, {"taddhita": taddhita, "base": base}, None)


def _krdanta_stems(lemma: str):
    """Participle stems built from a verbal lemma: root (+upasargas) + kṛt."""
    from vidyut.prakriya import Krt, Pratipadika

    for prefixes, entry, dhatu in _dhatu_candidates(lemma):
        d = _with_prefixes(prefixes, dhatu)
        for krt in _PARTICIPLE_KRTS:
            extra = {"krt": krt, **_dhatu_feats(prefixes, dhatu)}
            yield (Pratipadika.krdanta(d, getattr(Krt, krt)), citation_root(entry["dhatu_slp1"]),
                   extra, dhatu_info(entry["code"], entry))


def _subanta(surface: str, stems, morph: Morph) -> Reading | None:
    from vidyut.prakriya import Linga, Pada, Vacana, Vibhakti

    v = _vyakarana()
    lingas = [morph.linga] if morph.linga else list(_LINGA_ATTR)
    enclitic = _ENCLITIC.get((morph.vibhakti, morph.vacana))
    for prati, stem, extra, dhatu in stems:
        if not extra:  # basic stem: only a known word counts
            if stem not in PRONOUN_LEMMA.values() and not stem_attested(stem):
                continue
        elif "base" in extra and not stem_attested(extra["base"]):
            continue
        for linga in lingas:
            try:
                prakriyas = v.derive(Pada.Subanta(
                    pratipadika=prati, linga=getattr(Linga, _LINGA_ATTR[linga]),
                    vibhakti=getattr(Vibhakti, _VIBHAKTI_ATTR[morph.vibhakti]),
                    vacana=getattr(Vacana, _VACANA_ATTR[morph.vacana])))
            except Exception:  # vidyut rejects some stem/linga pairs
                logger.debug("subanta derive failed for %s (stem %s, %s)",
                             surface, stem, linga, exc_info=True)
                continue
            feats = {"vibhakti": morph.vibhakti, "vacana": morph.vacana,
                     "linga": linga, **extra}
            for p in prakriyas:
                if same_surface(p.text, surface):
                    return Reading(surface, stem, "subanta", feats, True, "vidyut",
                                   dhatu=dhatu, trace=_trace(p))
            # Only when vidyut does not derive the enclitic itself (0.4.0): 8.1.22 reader rule.
            if enclitic and stem in enclitic[0] and same_surface(enclitic[0][stem], surface):
                p = prakriyas[0] if prakriyas else None
                if p is not None:
                    feats.pop("linga")
                    note = (f"{enclitic[1]}: enclitic {enclitic[0][stem]} for {p.text} "
                            "(reader rule; not sentence-initial)")
                    return Reading(surface, stem, "subanta", feats, True,
                                   "vidyut+reader-rule", trace=_trace(p), notes=[note])
    return None


def taddhita_head(surface: str, base: str, suffix: str, morph: Morph) -> Reading | None:
    """pAtra + tvAt -> pAtratva (tva) ablative; pAtra + tAm -> pAtratA (tal)."""
    from vidyut.prakriya import Pratipadika, Taddhita

    name = {"tva": "tva", "tA": "tal"}.get(suffix)
    if name is None or not stem_attested(base) or not morph.vibhakti:
        return None
    stem = Pratipadika.taddhitanta(Pratipadika.basic(base), getattr(Taddhita, name))
    gender = "napuMsaka" if name == "tva" else "strI"
    m = Morph("nominal", vacana=morph.vacana, vibhakti=morph.vibhakti, linga=gender)
    return _subanta(surface, [(stem, base + suffix, {"taddhita": name, "base": base}, None)], m)


def _absolutive(surface: str, lemma: str) -> Reading | None:
    """ktvA / lyap (with upasargas): an indeclinable kṛdanta."""
    from vidyut.prakriya import Krt, Linga, Pada, Pratipadika, Vacana, Vibhakti

    v = _vyakarana()
    for prefixes, entry, dhatu in _dhatu_candidates(lemma):
        d = _with_prefixes(prefixes, dhatu)
        try:
            prakriyas = v.derive(Pada.Subanta(
                pratipadika=Pratipadika.krdanta(d, Krt.ktvA), linga=Linga.Pum,
                vibhakti=Vibhakti.Prathama, vacana=Vacana.Eka))
        except Exception:  # vidyut rejects some dhatu/krt pairs
            logger.debug("absolutive derive failed for %s (lemma %s)",
                         surface, lemma, exc_info=True)
            continue
        for p in prakriyas:
            if same_surface(p.text, surface):
                feats = {"krt": "lyap" if prefixes else "ktvA"}
                if prefixes:
                    feats["upasarga"] = "+".join(prefixes)
                return Reading(surface, citation_root(entry["dhatu_slp1"]), "avyaya", feats, True,
                               "vidyut", dhatu_info(entry["code"], entry), _trace(p))
    return None


def pausa_variants(surface: str) -> list[str]:
    """The word as written, then its pausa spelling: tatas -> tataH, kadAcid -> kadAcit."""
    out = [surface]
    for pat, rep in ((r"[sr]$", "H"), (r"d$", "t"), (r"g$", "k"), (r"q$", "w"), (r"b$", "p"),
                     (r"M$", "m"), (r"S$", "H")):
        v = re.sub(pat, rep, surface)
        if v not in out:
            out.append(v)
    return out


def _with_particle(surface: str) -> Reading | None:
    """kadAcana = kadA + cana, kaScit = kaH + cit: verify the host, keep the particle."""
    for particle in _PARTICLES:
        if surface.endswith(particle) and len(surface) > len(particle) + 1:
            host = surface[: -len(particle)]
            for h in dict.fromkeys((host, re.sub(r"S$", "H", host), re.sub(r"[YNM]$", "m", host))):
                cands = analyze_pada(h, limit=5)
                if cands:
                    c = cands[0]
                    return Reading(surface, surface, "avyaya" if "avyaya" in c.morph else "subanta",
                                   {"host": f"{c.lemma} ({c.morph})", "particle": particle},
                                   True, "kosha", trace=c.prakriya,
                                   notes=[f"{h} + indefinite particle {particle}"])
    return None


_MORPH_WORDS = {"la~w": "law", "la~N": "laN", "li~w": "liw", "lu~N": "luN", "lf~w": "lfw",
                "lu~w": "luw", "lo~w": "low", "li~N": "viDiliN"}


def _agreement(cand, lemma: str, morph: Morph) -> int:
    words = cand.morph.split()
    score = 4 * (cand.lemma == PRONOUN_LEMMA.get(lemma, lemma))
    if morph.kind == "unknown":  # no tags: trust real words over kosha oddities
        score += 3 * (cand.kind == "Tinanta") + 2 * bool(stem_attested(cand.lemma))
        score -= "samboDanam" in words
    if morph.kind in ("avyaya", "absolutive", "unknown"):
        score += 3 * ("avyaya" in words)
    if morph.kind == "verb":
        score += 2 * (cand.kind == "Tinanta")
        score += 2 * any(_MORPH_WORDS.get(w) in morph.lakaras for w in words)
        score += (morph.purusha in words) + (morph.vacana in words)
    else:
        score += 2 * (morph.vibhakti in words) + (morph.vacana in words) + (morph.linga in words)
        score -= 2 * (cand.kind == "Tinanta")
    return score


def _kosha_kind(cand) -> str:
    if cand.kind == "Tinanta":
        return "tinanta"
    return "avyaya" if "avyaya" in cand.morph.split() else "subanta"


def _from_kosha(surface: str, lemma: str, morph: Morph) -> Reading | None:
    cands = analyze_pada(surface, limit=20)
    if not cands:
        return None
    best = max(cands, key=lambda c: _agreement(c, lemma, morph))
    return Reading(surface, best.lemma, _kosha_kind(best), {"morph": best.morph}, True, "kosha",
                   trace=best.prakriya,
                   notes=[] if best.lemma == PRONOUN_LEMMA.get(lemma, lemma)
                   else [f"model lemma {lemma!r} did not verify; kosha reading chosen"])


def _alternatives(surface: str, chosen: Reading, limit: int = 3) -> list[dict[str, str]]:
    """Other verified readings worth showing (a different kind or lemma), credible only."""
    out: list[dict[str, str]] = []
    seen = {(chosen.kind, chosen.lemma)}
    for c in analyze_pada(surface, limit=20):
        kind = _kosha_kind(c)
        if (kind, c.lemma) in seen or "samboDanam" in c.morph:
            continue
        r = Reading(surface, c.lemma, kind, {"morph": c.morph}, True, "kosha")
        if not credible(r):
            continue
        seen.add((kind, c.lemma))
        out.append({"lemma": c.lemma, "kind": kind, "morph": c.morph})
        if len(out) == limit:
            break
    return out


_ENCLITIC_FORMS = {"te": ("yuzmad", "eka"), "me": ("asmad", "eka"), "vAm": ("yuzmad", "dvi"),
                   "nO": ("asmad", "dvi"), "vaH": ("yuzmad", "bahu"), "naH": ("asmad", "bahu")}


def _enclitic(surface: str) -> Reading | None:
    """Untagged te / me / vAm / nO / vaH / naH: the yuSmad/asmad enclitic (genitive)."""
    hit = _ENCLITIC_FORMS.get(re.sub(r"[sr]$", "H", surface))
    if hit is None:
        return None
    stem, vacana = hit
    return _subanta(surface, _basic_stems(stem),
                    Morph("nominal", vacana=vacana, vibhakti="zazWI"))


# Short words that are real; any other 1-2 letter kosha hit is treated as noise.
SHORT_WORDS = frozenset("ca vA hi tu na sa me te mA nu ha sma u A iva eva yaH yat tat tvam "
                        "aham vaH naH vAm nO kaH kim saH sA tA te ye yA ime".split())


def _sa_esa(surface: str) -> Reading | None:
    """sa / eza before a consonant: tad / etad nominative with su dropped (6.1.132)."""
    stem = {"sa": "tad", "eza": "etad"}.get(surface)
    if stem is None:
        return None
    r = _subanta(surface + "H", _basic_stems(stem),
                 Morph("nominal", vacana="eka", vibhakti="praTamA", linga="puM"))
    if r is None:
        return None
    r.surface, r.source = surface, "vidyut+reader-rule"
    r.notes.append(f"6.1.132 etattadoH sulopo 'kor anaYsamAse hali: {surface}H -> {surface} "
                   "before a consonant (reader rule)")
    return r


def credible(r: Reading) -> bool:
    """Verified and built on a real word, not a kosha oddity (used to vet re-splits)."""
    if not r.verified:
        return False
    if len(r.surface) <= 2 and r.surface not in SHORT_WORDS:
        return False
    if r.source.startswith("vidyut"):
        return True
    if r.kind == "tinanta":  # kosha verb: its root must be a Dhātupāṭha root
        from sanskrit_analyzer.dhatu.dhatupatha import get_dhatu_kosha, strip_anubandhas
        k = get_dhatu_kosha()  # kosha lemmas are clean roots (as, kf); upadeSas need stripping
        return bool(k.lookup(r.lemma) or k.lookup(strip_anubandhas(r.lemma)))
    from sanskrit_analyzer import lexicon
    return any(lexicon.lookup(v) for v in _spelling_variants(r.lemma)) or r.surface in SHORT_WORDS


def verify_word(surface: str, lemma: str, morph: Morph,
                after_ma: bool = False) -> Reading:
    """Best verified reading of one word, or the model's reading marked unverified.

    ``after_ma``: the prohibitive mā occurs just before (aorist without augment).
    """
    reading = None
    try:
        if morph.kind == "verb":
            reading = _tinanta(surface, lemma, morph, augmentless=after_ma)
        elif morph.kind == "nominal":
            reading = _subanta(surface, _basic_stems(lemma), morph) \
                or _subanta(surface, _krdanta_stems(lemma), morph)
        elif morph.kind == "participle":
            reading = _subanta(surface, _krdanta_stems(lemma), morph) \
                or _subanta(surface, _basic_stems(lemma), morph)
        elif morph.kind == "absolutive":
            reading = _absolutive(surface, lemma)
        if reading is None and morph.kind in ("unknown", "nominal", "avyaya"):
            reading = _sa_esa(surface)
        if reading is None and morph.kind == "unknown":
            reading = _enclitic(surface)
        if reading is None and morph.kind != "compound_member":
            for form in pausa_variants(surface):
                reading = _from_kosha(form, lemma, morph) or _with_particle(form)
                if reading is not None:
                    reading.surface = surface
                    break
    except Exception as exc:  # a derivation crash must not sink the whole verse
        logger.warning("verify_word(%s) failed: %s", surface, exc)
    if reading is not None:
        reading.alternatives = _alternatives(surface, reading)
        return reading
    kind = {"compound_member": "compound_member", "avyaya": "avyaya",
            "absolutive": "avyaya"}.get(morph.kind, "unknown")
    feats = {k: v for k, v in (("vibhakti", morph.vibhakti), ("vacana", morph.vacana),
                               ("linga", morph.linga), ("purusha", morph.purusha)) if v}
    return Reading(surface, lemma, kind, feats, False, "model",
                   notes=["no Paninian derivation found; model reading, unverified"])
