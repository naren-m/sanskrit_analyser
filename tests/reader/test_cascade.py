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
        ([_w("rAmaH"), _w("gacCati")], "rAmogacCati", 0.80, False),   # all verified, covered
        ([_w("rAmaH"), _w("gacCati", False)], "rAmogacCati", 0.80, True),  # one unverified
        ([_w("rAmaH")], "rAmogacCati", 0.80, True),                    # a word dropped
        ([], "rAmogacCati", 0.80, True),                               # nothing proposed
        ([_w("rAmaH"), _w("gacCati")], "rAmogacCati", 0.99, True),     # strict threshold
    ],
)
def test_needs_fallback(words, text, min_cov, want) -> None:
    assert needs_fallback(words, text, min_cov) is want


@pytest.fixture
def fake(monkeypatch):
    """Stub both proposers and verification; record which proposers ran."""
    calls: list[str] = []
    outputs = {"slm": [Hypothesis("rAmaH", "rAma", "")], "byt5": [Hypothesis("rAmaH", "rAma", ""),
                                                                   Hypothesis("gacCati", "gam", "")]}

    def propose(text, name):
        calls.append(name)
        return outputs[name], name

    def assemble(hyps):
        return [{"surface": h.surface, "verified": True, "index": i} for i, h in enumerate(hyps)]

    monkeypatch.setattr(read, "_propose", propose)
    monkeypatch.setattr(read, "_assemble", assemble)
    monkeypatch.setattr(read, "normalize", lambda t: type("N", (), {"slp1": t})())
    monkeypatch.setattr(read, "CASCADE_MIN_COVERAGE", 0.80)   # the real value is tuned on the bench
    return calls, outputs


def test_cascade_keeps_a_confident_char_model_reading(fake) -> None:
    calls, outputs = fake
    outputs["slm"] = outputs["byt5"]                      # char model covers the line
    words, label = read.read_words("rAmogacCati", "cascade")
    assert calls == ["slm"] and label == "cascade:slm"
    assert [w["surface"] for w in words] == ["rAmaH", "gacCati"]


def test_cascade_falls_back_when_a_word_is_missing(fake) -> None:
    calls, _ = fake                                       # slm dropped "gacCati"
    words, label = read.read_words("rAmogacCati", "cascade")
    assert calls == ["slm", "byt5"] and label == "cascade:byt5"
    assert [w["surface"] for w in words] == ["rAmaH", "gacCati"]
    assert read.CASCADE_STATS["fallback"] >= 1
