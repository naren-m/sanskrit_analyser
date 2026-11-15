"""Meaning-layer checks and retry loop, offline (fake chat function)."""
from __future__ import annotations

import pytest

from sanskrit_analyzer.reader.llm import build_prompt, check, interpret


def _word(i, iast, kind, lemma, **features):
    return {"index": i, "surface_iast": iast, "kind": kind, "lemma": lemma,
            "features": features, "verified": True, "alternatives": []}


RECORD = {
    "input": {"iast": "rāmaḥ vanam gacchati"},
    "words": [
        _word(0, "rāmaḥ", "subanta", "rAma", vibhakti="praTamA", vacana="eka", linga="puM"),
        _word(1, "vanam", "subanta", "vana", vibhakti="dvitIyA", vacana="eka", linga="napuMsaka"),
        _word(2, "gacchati", "tinanta", "gam", lakara="law", purusha="praTama", vacana="eka"),
    ],
}
GOOD = {
    "anvaya": [0, 1, 2],
    "words": [{"index": 0, "role": "subject", "gloss": "Rama"},
              {"index": 1, "role": "object", "gloss": "forest"},
              {"index": 2, "role": "verb", "gloss": "goes"}],
    "translation": "Rama goes to the forest.",
    "explanation": "Rama is the doer.",
}


def _with(**changes):
    return {**GOOD, **changes}


@pytest.mark.parametrize(
    ("answer", "error_fragment"),
    [
        (GOOD, None),
        (_with(anvaya=[0, 2]), "anvaya must use each index"),
        (_with(words=GOOD["words"][:2]), "missing word entries"),
        (_with(words=[{"index": 0, "role": "verb", "gloss": "Rama"}] + GOOD["words"][1:]),
         "not a finite verb"),
        (_with(words=[GOOD["words"][0], {"index": 1, "role": "subject", "gloss": "forest"},
                      GOOD["words"][2]]), "accusative, not a subject case"),
        (_with(words=[{"index": 0, "role": "hero", "gloss": "Rama"}] + GOOD["words"][1:]),
         "not one of the allowed roles"),
        (_with(translation=""), "empty translation"),
    ],
)
def test_check(answer, error_fragment) -> None:
    errors = check(RECORD, answer)
    if error_fragment is None:
        assert errors == []
    else:
        assert any(error_fragment in e for e in errors), errors


def test_interpret_retries_once_with_the_errors() -> None:
    calls = []

    def chat(messages, model):
        calls.append(messages)
        return _with(anvaya=[2]) if len(calls) == 1 else GOOD

    out = interpret(RECORD, model="fake", chat=chat)
    assert out["checks_passed"] and out["attempts"] == 2
    assert "anvaya must use each index" in calls[1][-1]["content"]


def test_interpret_reports_a_dead_llm() -> None:
    def chat(messages, model):
        raise ConnectionError("refused")

    out = interpret(RECORD, model="fake", chat=chat)
    assert "LLM call failed" in out["error"]


def test_prompt_lists_grammar_not_raw_verse_only() -> None:
    prompt = build_prompt(RECORD)
    assert "2. gacchati | lemma gam | finite verb, present, 3rd person, singular" in prompt
