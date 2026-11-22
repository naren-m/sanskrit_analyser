"""Cascade proposer: char model first, ByT5 only when the char model is in doubt."""
from __future__ import annotations

import pytest

from sanskrit_analyzer.reader import read
from sanskrit_analyzer.reader.read import Hypothesis, needs_fallback


def _w(surface: str, verified: bool = True) -> dict:
    return {"surface": surface, "verified": verified}


@pytest.mark.parametrize(
    ("words", "text", "min_cov", "want"),
    [
        ([_w("rAmaH"), _w("gacCati")], "rAmogacCati", 0.80, False),        # verified, covered
        ([_w("rAmaH"), _w("gacCati", False)], "rAmogacCati", 0.80, True),  # one unverified
        ([_w("rAmaH")], "rAmogacCati", 0.80, True),                        # a word dropped
        ([], "rAmogacCati", 0.80, True),                                   # nothing proposed
        ([_w("rAmaH"), _w("gacCati")], "rAmogacCati", 0.99, True),         # strict threshold
    ],
)
def test_needs_fallback(words, text, min_cov, want) -> None:
    assert needs_fallback(words, text, min_cov) is want


FULL = [Hypothesis("rAmaH", "rAma", ""), Hypothesis("gacCati", "gam", "")]
DROPPED = FULL[:1]


@pytest.mark.parametrize(
    ("slm_hyps", "slm_verified", "want_calls", "want_label"),
    [
        (FULL, True, ["slm"], "cascade:slm"),                        # verified and covered
        (FULL, False, ["slm", "byt5"], "cascade+byt5:byt5"),         # unverified word
        (DROPPED, True, ["slm", "byt5"], "cascade+byt5:byt5"),       # low coverage
    ],
)
def test_cascade(monkeypatch, slm_hyps, slm_verified, want_calls, want_label) -> None:
    calls: list[str] = []
    outputs = {"slm": slm_hyps, "byt5": FULL}

    def propose(text, name):
        calls.append(name)
        return outputs[name], name

    def assemble(hyps):
        ok = slm_verified or hyps is FULL and calls[-1] == "byt5"
        return [{"surface": h.surface, "verified": ok} for h in hyps]

    monkeypatch.setattr(read, "_propose", propose)
    monkeypatch.setattr(read, "_assemble", assemble)
    monkeypatch.setattr(read, "normalize", lambda t: type("N", (), {"slp1": t})())
    monkeypatch.setattr(read, "CASCADE_MIN_COVERAGE", 0.80)
    words, label = read.read_words("rAmogacCati", "cascade")
    assert calls == want_calls and label == want_label
    assert [w["surface"] for w in words] == ["rAmaH", "gacCati"]
