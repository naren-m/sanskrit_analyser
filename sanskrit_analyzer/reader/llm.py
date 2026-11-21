"""Meaning layer: anvaya, roles, word glosses, translation, explanation.

The LLM sees only the verified per-word JSON from ``reader.read`` — never the
raw verse alone — and must answer by word index. Its answer is then checked
against the grammar it was given:

- the anvaya is a permutation of every word index;
- every word has a gloss;
- a word cast as the verb is a tiṅanta; a nominative-only role (kartā in an
  active sentence) is a praTamA word.

On a failed check the model gets one retry with the errors listed. Whatever
survives is labelled ``source="llm"``: it is interpretation, not proof. The
model never cites a sūtra.
"""
from __future__ import annotations

import json
import logging
import os
import urllib.request
from typing import Any

from sanskrit_analyzer.config import ollama_url

logger = logging.getLogger(__name__)

DEFAULT_MODEL = os.environ.get("SANSKRIT_READER_MODEL", "qwen3.8:27b")
OLLAMA_URL = ollama_url()

_CASE = {"praTamA": "nominative", "dvitIyA": "accusative", "tftIyA": "instrumental",
         "caturTI": "dative", "paYcamI": "ablative", "zazWI": "genitive",
         "saptamI": "locative", "samboDanam": "vocative"}
_NUMBER = {"eka": "singular", "dvi": "dual", "bahu": "plural"}
_GENDER = {"puM": "masculine", "strI": "feminine", "napuMsaka": "neuter"}
_PERSON = {"praTama": "3rd person", "maDyama": "2nd person", "uttama": "1st person"}
_TENSE = {"law": "present", "laN": "imperfect", "liw": "perfect", "luN": "aorist",
          "lfw": "future", "luw": "periphrastic future", "low": "imperative",
          "viDiliN": "optative", "ASIrliN": "benedictive"}
_KRT = {"kta": "past passive participle", "ktavatu": "past active participle",
        "Satf": "present active participle", "SAnac": "present middle participle",
        "tavya": "gerundive", "anIyar": "gerundive", "yat": "gerundive", "Ryat": "gerundive"}

ROLES = ("verb", "subject", "object", "instrument", "recipient", "source", "possessor",
         "location", "addressee", "modifier", "predicate", "particle", "other")

_SYSTEM = """You explain Sanskrit verses to a learner in plain English.
You get every word of one verse with its grammar, already verified by a Paninian engine.
Trust that grammar. Do not change it. Do not cite sutra numbers.
A word may list "OR ..." alternative readings: pick the one the context needs.
Answer with JSON only, in this shape:
{"anvaya": [word indices in natural prose order],
 "words": [{"index": i, "role": one of ROLES, "gloss": "short English meaning in context"}],
 "translation": "one faithful English sentence or two",
 "explanation": "3-5 short sentences: who does what, and one thing a learner should notice"}
Use every index exactly once in "anvaya" and in "words".
ROLES: """ + ", ".join(ROLES)


def _describe(w: dict[str, Any]) -> str:
    f = w.get("features") or {}
    parts: list[str] = []
    if w["kind"] == "tinanta":
        parts += ["finite verb", _TENSE.get(f.get("lakara", ""), f.get("lakara", "")),
                  _PERSON.get(f.get("purusha", ""), ""), _NUMBER.get(f.get("vacana", ""), "")]
        if f.get("upasarga"):
            parts.append(f"prefix {f['upasarga']}")
    elif w["kind"] == "subanta":
        parts += [_KRT.get(f.get("krt", ""), "noun/adjective/pronoun"),
                  _CASE.get(f.get("vibhakti", ""), ""), _GENDER.get(f.get("linga", ""), ""),
                  _NUMBER.get(f.get("vacana", ""), "")]
        if f.get("morph"):
            parts.append(f["morph"])
    else:
        parts.append({"avyaya": "indeclinable"}.get(w["kind"], w["kind"]))
    dh = w.get("dhatu") or {}
    if dh.get("root"):
        parts.append(f"root {dh['root']} ({dh.get('gloss_en') or dh.get('artha') or '?'})")
    members = w.get("compound_members")
    if members:
        parts.append("compound of " + " + ".join(m["lemma"] for m in members))
    if not w.get("verified"):
        parts.append("UNVERIFIED reading")
    for alt in w.get("alternatives") or []:
        parts.append(f"OR {alt['kind']} {alt['lemma']} ({alt['morph']})")
    return ", ".join(p for p in parts if p)


def build_prompt(record: dict[str, Any]) -> str:
    lines = [f"Verse (IAST): {record['input']['iast']}", "Words:"]
    for w in record["words"]:
        surface = w.get("compound_surface_iast") or w["surface_iast"]
        lines.append(f"{w['index']}. {surface} | lemma {w['lemma']} | {_describe(w)}")
    return "\n".join(lines)


def check(record: dict[str, Any], answer: dict[str, Any]) -> list[str]:
    """Errors in an LLM answer, judged against the verified grammar."""
    words = {w["index"]: w for w in record["words"]}
    errors: list[str] = []
    anvaya = answer.get("anvaya")
    if not isinstance(anvaya, list) or sorted(anvaya) != sorted(words):
        errors.append(f"anvaya must use each index 0..{len(words) - 1} exactly once")
    glossed = {item["index"]: item for item in answer.get("words") or []
               if isinstance(item, dict) and item.get("index") in words}
    missing = sorted(set(words) - set(glossed))
    if missing:
        errors.append(f"missing word entries for indices {missing}")
    for i, item in glossed.items():
        w, role = words[i], item.get("role")
        if role not in ROLES:
            errors.append(f"word {i}: role {role!r} is not one of the allowed roles")
        alt_verb = any(a["kind"] == "tinanta" for a in w.get("alternatives") or [])
        if role == "verb" and w["kind"] != "tinanta" and not alt_verb \
                and not (w.get("features") or {}).get("krt"):
            errors.append(f"word {i} ({w['surface_iast']}) is not a finite verb or participle")
        if role == "subject" and w["kind"] == "subanta" and \
                (w.get("features") or {}).get("vibhakti") not in (None, "praTamA", "tftIyA"):
            errors.append(f"word {i} ({w['surface_iast']}) is "
                          f"{_CASE.get(w['features']['vibhakti'])}, not a subject case")
        if not item.get("gloss"):
            errors.append(f"word {i}: empty gloss")
    if not answer.get("translation"):
        errors.append("empty translation")
    return errors


def _chat(messages: list[dict[str, str]], model: str) -> dict[str, Any]:
    body = json.dumps({"model": model, "messages": messages, "stream": False,
                       "format": "json", "think": False,
                       "options": {"temperature": 0, "num_ctx": 8192}}).encode()
    req = urllib.request.Request(f"{OLLAMA_URL}/api/chat", data=body,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=600) as resp:
        content = json.loads(resp.read())["message"]["content"]
    return json.loads(content)


def interpret(record: dict[str, Any], model: str | None = None,
              chat=_chat) -> dict[str, Any]:
    model = model or DEFAULT_MODEL
    messages = [{"role": "system", "content": _SYSTEM},
                {"role": "user", "content": build_prompt(record)}]
    answer: dict[str, Any] = {}
    errors: list[str] = []
    for attempt in range(2):
        try:
            answer = chat(messages, model)
        except Exception as exc:
            logger.warning("reader LLM call failed (model %s)", model, exc_info=True)
            return {"source": "llm", "model": model, "error": f"LLM call failed: {exc}"}
        errors = check(record, answer)
        if not errors:
            break
        messages += [{"role": "assistant", "content": json.dumps(answer, ensure_ascii=False)},
                     {"role": "user", "content": "Fix these problems and answer again:\n- "
                      + "\n- ".join(errors)}]
    return {"source": "llm", "model": model, "attempts": attempt + 1,
            "checks_passed": not errors, "check_errors": errors, **answer}


# --- translation-only mode ------------------------------------------------------

_TRANSLATE_SYSTEM = """You translate one Sanskrit verse into plain, faithful English.
You get the verse and every word with its grammar, already verified by a Paninian engine.
Use that grammar: who does what, to whom, when. Do not add commentary or sutra numbers.
Answer with JSON only: {"translation": "one or two English sentences"}"""


def _short(w: dict[str, Any]) -> str:
    surface = w.get("compound_surface_iast") or w["surface_iast"]
    return f"{surface} ({w['lemma']}: {_describe(w)})"


def build_translate_prompt(record: dict[str, Any]) -> str:
    return "\n".join([f"Verse (IAST): {record['input']['iast']}", "Words:"]
                     + [f"- {_short(w)}" for w in record["words"]])


def translate(record: dict[str, Any], model: str | None = None, chat=_chat) -> dict[str, Any]:
    """English translation only, grounded in the verified words. One retry if empty."""
    model = model or DEFAULT_MODEL
    messages = [{"role": "system", "content": _TRANSLATE_SYSTEM},
                {"role": "user", "content": build_translate_prompt(record)}]
    for attempt in (1, 2):
        try:
            answer = chat(messages, model)
        except Exception as exc:
            logger.warning("translate LLM call failed (model %s)", model, exc_info=True)
            return {"source": "llm", "model": model, "attempts": attempt,
                    "error": f"LLM call failed: {exc}"}
        text = (answer or {}).get("translation", "").strip()
        if text:
            return {"source": "llm", "model": model, "attempts": attempt, "translation": text}
        messages += [{"role": "assistant", "content": json.dumps(answer or {})},
                     {"role": "user",
                      "content": 'The "translation" field was empty. Answer again.'}]
    return {"source": "llm", "model": model, "attempts": 2, "error": "empty translation twice"}
