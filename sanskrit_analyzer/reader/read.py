"""One śloka in, a structured reading out.

Pipeline: normalize -> chandas -> ByT5 segmentation + tag hypothesis ->
per-word vidyut verification -> compound grouping -> (optional) LLM layer for
anvaya, word glosses, translation and a simple explanation. The LLM sees only
the verified JSON and its output is checked against it (``reader.llm``).
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from sanskrit_analyzer.models.scripts import Script
from sanskrit_analyzer.prakriya import chandas as chandas_mod
from sanskrit_analyzer.prakriya.engine import _chandas_record
from sanskrit_analyzer.prakriya.normalize import normalize
from sanskrit_analyzer.reader.derive import credible, stem_attested, taddhita_head, verify_word
from sanskrit_analyzer.reader.sandhi import vowel_join
from sanskrit_analyzer.reader.tags import Morph, decode
from sanskrit_analyzer.utils import transliterate

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Hypothesis:
    surface: str   # SLP1
    lemma: str     # SLP1
    tags: str


def _iast_to_slp1(s: str) -> str:
    return transliterate(s, Script.IAST, Script.SLP1)


def _slp1_to(s: str, script: Script) -> str:
    return transliterate(s, Script.SLP1, script)


def _byt5_hypotheses(text_slp1: str) -> list[Hypothesis] | None:
    from sanskrit_analyzer.dhatu.byt5_ranker import get_shared_adapter

    engine = get_shared_adapter()._ensure_engine()
    if engine is None or not engine.is_available:
        return None
    result = engine.analyze_sync(text_slp1)
    out = []
    for seg in result.segments or []:
        surface = _iast_to_slp1(seg.surface or "")
        if not surface.strip("/|'"):
            continue  # daṇḍa tokens
        out.append(Hypothesis(surface, _iast_to_slp1(seg.lemma or seg.surface),
                              seg.morphology or ""))
    return out or None


def _dp_hypotheses(text: str) -> list[Hypothesis]:
    from sanskrit_analyzer.deep_read import DeepRead

    tokens = DeepRead().analyze(text, use_byt5=False).to_dict()["tokens"]
    out = []
    for t in tokens:
        slp = t.get("slp1") or transliterate(t["surface"], Script.DEVANAGARI, Script.SLP1)
        if slp.strip("/|'"):
            lemma = (t.get("analyses") or [{}])[0].get("lemma") or slp
            out.append(Hypothesis(slp, lemma, ""))
    return out


def _add_scripts(reading: dict[str, Any]) -> None:
    reading["surface_iast"] = _slp1_to(reading["surface"], Script.IAST)
    reading["surface_devanagari"] = _slp1_to(reading["surface"], Script.DEVANAGARI)


def _verify(h: Hypothesis, morph: Morph, after_ma: bool) -> dict[str, Any]:
    r = verify_word(h.surface, h.lemma, morph, after_ma)
    if morph.kind == "compound_member":
        where = stem_attested(h.lemma) or stem_attested(h.surface)
        r.verified, r.source = bool(where), f"{where}-stem" if where else "model"
        r.notes = [] if where else ["member stem not attested in kosha or lexicon; unverified"]
    d = r.to_dict()
    if h.tags == "resplit":
        d["notes"].append("re-split by the lexicon DP segmenter: the model's split did not verify")
    d["hypothesis"] = {"lemma": h.lemma, "tags": h.tags}
    return d


def _resplit(h: Hypothesis) -> list[Hypothesis] | None:
    """Re-split a word the model segmented badly, with the lexicon DP segmenter.

    Kept only when it yields two or more parts and every part verifies.
    """
    parts = _dp_hypotheses(_slp1_to(h.surface, Script.DEVANAGARI))
    if len(parts) < 2:
        return None
    # The DP's own first lemma is not a hypothesis: verify parts untagged and unlemmatised.
    parts = [Hypothesis(p.surface, "", "resplit") for p in parts]
    if all(credible(verify_word(p.surface, "", Morph("unknown"))) for p in parts):
        return parts
    return None


def _repair(hyps: list[Hypothesis]) -> list[Hypothesis]:
    """Re-split words whose model reading is not credible.

    Tries the word alone, then joined with its left neighbour, then with its
    right one: the model can put a junction vowel on the wrong side
    (rAjA + ArAjan for rAjArAjan, cakuruta + ivaSe for cakurutevaSe).
    """
    def ok(h: Hypothesis) -> bool:
        morph = decode(h.tags)
        return morph.kind == "compound_member" or credible(verify_word(h.surface, h.lemma, morph))

    out: list[Hypothesis] = []
    i = 0
    while i < len(hyps):
        h = hyps[i]
        if ok(h):
            out.append(h)
            i += 1
            continue
        parts, used_next = _resplit(h), False
        if parts is None and out:
            parts = _resplit(Hypothesis(vowel_join(out[-1].surface, h.surface), "", ""))
            if parts:
                out.pop()
        if parts is None and i + 1 < len(hyps):
            parts = _resplit(Hypothesis(vowel_join(h.surface, hyps[i + 1].surface), "", ""))
            used_next = parts is not None
        if parts:
            out.extend(parts)
        else:
            out.append(h)
        i += 2 if used_next else 1
    return out


def read_words(text: str) -> tuple[list[dict[str, Any]], str]:
    """Segment and verify. Returns (words, segmenter label)."""
    n = normalize(text)
    hyps, label = None, "byt5"
    try:
        hyps = _byt5_hypotheses(n.slp1)
    except Exception as exc:
        logger.warning("ByT5 unavailable: %s", exc)
    if not hyps:
        hyps, label = _dp_hypotheses(text), "dp"
    hyps = _repair(hyps)

    words: list[dict[str, Any]] = []
    members: list[dict[str, Any]] = []
    recent: list[str] = []  # last surfaces, for mA + aorist
    for h in hyps:
        morph = decode(h.tags)
        reading = _verify(h, morph, "mA" in recent[-3:])
        _add_scripts(reading)
        if morph.kind == "compound_member":
            members.append(reading)
            continue
        if members and h.lemma in ("tva", "tA"):
            # pAtra-tvAt is one taddhita word (pAtratva): it absorbs the last
            # member, and any earlier members still form a compound with it.
            last = members[-1]
            merged = taddhita_head(last["surface"] + h.surface, last["lemma"], h.lemma, morph)
            if merged is not None:
                members.pop()
                reading.update(merged.to_dict())
                _add_scripts(reading)
        if members:
            reading["compound_members"] = members + [dict(reading)]
            reading["compound_surface_iast"] = "-".join(
                [_slp1_to(m["surface"], Script.IAST) for m in members] + [reading["surface_iast"]])
            members = []
        reading["index"] = len(words)
        words.append(reading)
        recent.append(h.surface)
    if members:  # trailing members with no head: keep them visible
        for m in members:
            m["index"] = len(words)
            words.append(m)
    return words, label


def read_sloka(text: str, llm: bool = False, model: str | None = None) -> dict[str, Any]:
    n = normalize(text)
    record: dict[str, Any] = {
        "input": {"raw": n.raw, "script": n.script, "slp1": n.slp1,
                  "iast": _slp1_to(n.slp1, Script.IAST)},
        "chandas": None,
    }
    if n.words and chandas_mod.is_available():
        try:
            record["chandas"] = _chandas_record(chandas_mod.identify(n.slp1))
        except Exception as exc:
            logger.warning("chandas failed: %s", exc)
    words, label = read_words(text)
    record["segmenter"] = label
    record["words"] = words
    record["stats"] = {
        "words": len(words),
        "verified": sum(w["verified"] for w in words),
        "by_source": {s: sum(w["source"] == s for w in words)
                      for s in sorted({w["source"] for w in words})},
    }
    if llm:
        from sanskrit_analyzer.reader.llm import interpret
        record["interpretation"] = interpret(record, model=model)
    return record
