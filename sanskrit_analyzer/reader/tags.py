"""Decode the compact morphology tags of the ByT5-Sanskrit SLM task.

The model (``chronbmm/sanskrit5-multitask``) writes DCS-style tags. The
scheme below was read off real outputs on known forms (see
``tests/reader/test_tags.py``):

- nominal: number + case + gender, e.g. ``PLNe`` = plural locative neuter.
  1st/2nd-person pronouns carry no gender (``SG``).
- finite verb: number + tense + person + mood (``SPr3Im``), or
  number + person + tense + mood (``S2ImIn``).
- participle: number + case + ``Pa`` + tense + gender (``SNPaPsNe``).
- ``U`` indeclinable, ``Co`` absolutive (ktvā/lyap), ``Cp`` / ``PaCp`` compound
  member.
- ``Gd`` after a nominal tag: gerundive (``SNMGd`` = ślāghanīyaḥ).
- trailing suffixes: ``Pv`` passive (karmaṇi), ``Pe`` periphrastic perfect,
  ``Th`` (meaning unclear, ignored).

Tags are a *hypothesis*. The reader only trusts a reading that vidyut
regenerates to the observed surface.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

_VACANA = {"S": "eka", "Du": "dvi", "P": "bahu"}
_VIBHAKTI = {"N": "praTamA", "A": "dvitIyA", "I": "tftIyA", "D": "caturTI",
             "Ab": "paYcamI", "B": "paYcamI", "G": "zazWI", "L": "saptamI", "V": "samboDanam"}
_LINGA = {"M": "puM", "F": "strI", "Ne": "napuMsaka"}
_PURUSHA = {"3": "praTama", "2": "maDyama", "1": "uttama"}

# (tense, mood) -> candidate lakāras. "Ps" covers imperfect, perfect and aorist.
_LAKARAS = {
    ("Pr", "In"): ("law",), ("Pr", "Im"): ("low",), ("Pr", "O"): ("viDiliN", "ASIrliN"),
    ("Ps", "In"): ("laN", "liw", "luN"), ("Ps", ""): ("laN", "liw", "luN"),
    ("Im", "In"): ("laN",), ("Fu", "In"): ("lfw", "luw"),
}
_ALL_LAKARAS = ("law", "laN", "liw", "luN", "lfw", "luw", "low", "viDiliN")
_SIMPLE = {"U": "avyaya", "Co": "absolutive", "Cp": "compound_member", "PaCp": "compound_member"}

_NUM = r"(Du|S|P)"
_CASE = r"(Ab|N|A|I|D|B|G|L|V)"
_GEN = r"(Ne|M|F)?"
_NOMINAL = re.compile(rf"^{_NUM}{_CASE}{_GEN}$")
_GERUNDIVE = re.compile(rf"^{_NUM}{_CASE}{_GEN}Gd$")
_SUFFIX = r"(Pv|Pe|Th)?"
_PARTICIPLE = re.compile(rf"^{_NUM}{_CASE}Pa(?:Pr|Ps|Fu)?{_GEN}{_SUFFIX}$")
_VERB_TP = re.compile(rf"^{_NUM}(Pr|Ps|Fu|Im)([123])(In|Im|O)?{_SUFFIX}$")
_VERB_PT = re.compile(rf"^{_NUM}([123])(Pr|Ps|Fu|Im)(In|Im|O)?{_SUFFIX}$")


@dataclass(frozen=True)
class Morph:
    kind: str  # nominal | participle | verb | avyaya | absolutive | compound_member | unknown
    vacana: str | None = None
    vibhakti: str | None = None
    linga: str | None = None
    purusha: str | None = None
    lakaras: tuple[str, ...] = ()
    prayoga: str = "kartari"


def _prayoga(suffix: str | None) -> str:
    return "karmaRi" if suffix == "Pv" else "kartari"


def _verb(num: str, tense: str, person: str, mood: str | None, suffix: str | None) -> Morph:
    lakaras = ("liw",) if suffix == "Pe" else _LAKARAS.get((tense, mood or ""), _ALL_LAKARAS)
    return Morph("verb", vacana=_VACANA[num], purusha=_PURUSHA[person], lakaras=lakaras,
                 prayoga=_prayoga(suffix))


def decode(tag: str) -> Morph:
    """Tag string -> :class:`Morph`. Unknown shapes decode to kind ``unknown``."""
    tag = (tag or "").strip()
    if tag in _SIMPLE:
        return Morph(_SIMPLE[tag])
    if m := _NOMINAL.match(tag):
        return Morph("nominal", vacana=_VACANA[m[1]], vibhakti=_VIBHAKTI[m[2]],
                     linga=_LINGA.get(m[3] or ""))
    if m := _GERUNDIVE.match(tag):  # SNMGd: ślāghanīyaḥ (tavya / anīyar / yat)
        return Morph("participle", vacana=_VACANA[m[1]], vibhakti=_VIBHAKTI[m[2]],
                     linga=_LINGA.get(m[3] or ""))
    if m := _PARTICIPLE.match(tag):
        return Morph("participle", vacana=_VACANA[m[1]], vibhakti=_VIBHAKTI[m[2]],
                     linga=_LINGA.get(m[3] or ""), prayoga=_prayoga(m[4]))
    if m := _VERB_TP.match(tag):
        return _verb(m[1], m[2], m[3], m[4], m[5])
    if m := _VERB_PT.match(tag):
        return _verb(m[1], m[3], m[2], m[4], m[5])
    return Morph("unknown")
