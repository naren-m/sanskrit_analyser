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


@pytest.mark.parametrize(
    ("words", "licensed", "want"),
    [
        ([_w("rAmaH"), _w("gacCati")], True, None),
        ([_w("rAmaH"), _w("gacCati")], False, "unlicensed"),
        ([_w("rAmaH"), _w("gacCati", False)], False, "unverified"),   # unverified beats unlicensed
        ([_w("rAmaH")], False, "coverage"),                           # coverage beats unlicensed
        ([], True, "unverified"),
    ],
)
def test_fallback_reason(monkeypatch, words, licensed, want) -> None:
    monkeypatch.setattr(read, "split_is_licensed", lambda t, p: type("L", (), {"ok": licensed})())
    assert read.fallback_reason(words, "rAmogacCati", 0.80) == want


FULL = [Hypothesis("rAmaH", "rAma", ""), Hypothesis("gacCati", "gam", "")]
DROPPED = FULL[:1]


@pytest.mark.parametrize(
    ("slm_hyps", "slm_verified", "want_calls", "want_label"),
    [
        (FULL, True, ["slm"], "cascade:slm"),                        # verified and covered
        (FULL, False, ["slm", "byt5"], "cascade+byt5[unverified]:byt5"),  # unverified word
        (DROPPED, True, ["slm", "byt5"], "cascade+byt5[coverage]:byt5"),  # low coverage
    ],
)
def test_cascade(monkeypatch, slm_hyps, slm_verified, want_calls, want_label) -> None:
    monkeypatch.setattr(read, "split_is_licensed", lambda t, p: type("L", (), {"ok": True})())
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


@pytest.mark.parametrize(
    ("proposer", "licensed", "want_calls", "want_label", "want_first"),
    [
        ("cascade", {"slm": False, "byt5": True}, ["slm", "byt5"],
         "cascade+byt5[unlicensed]:byt5", "gacCati"),                     # fallback, licensed wins
        ("cascade", {"slm": False, "byt5": False}, ["slm", "byt5"],
         "cascade+byt5[unlicensed]:slm", "gacCati"),                      # neither: score, then ByT5
        ("best", {"slm": True, "byt5": False}, ["byt5", "slm"], "best:slm", "gacCati"),
        ("best", {"slm": False, "byt5": True}, ["byt5", "slm"], "best:byt5", "gacCati"),
    ],
)
def test_licensed_outranks_score(monkeypatch, proposer, licensed, want_calls, want_label,
                                 want_first) -> None:
    """A licensed split beats an unlicensed one even when the unlicensed one scores higher."""
    calls: list[str] = []
    hyps = {"slm": FULL, "byt5": FULL}
    cur: dict[str, str] = {}

    def propose(text, name):
        calls.append(name)
        cur["name"] = name
        return hyps[name], name

    def assemble(h):
        # slm gets a perfect score; byt5 is marked unverified (lower score)
        return [{"surface": x.surface, "verified": cur["name"] == "slm", "who": cur["name"]} for x in h]

    def lic(t, padas):
        return type("L", (), {"ok": licensed[words_who[0]]})()

    words_who = ["slm"]
    real_cov = read.coverage

    def cov(t, ws):
        words_who[0] = ws[0]["who"] if ws else "slm"
        return real_cov(t, ws)

    monkeypatch.setattr(read, "_propose", propose)
    monkeypatch.setattr(read, "_assemble", assemble)
    monkeypatch.setattr(read, "coverage", cov)
    monkeypatch.setattr(read, "split_is_licensed", lic)
    monkeypatch.setattr(read, "normalize", lambda t: type("N", (), {"slp1": t})())
    monkeypatch.setattr(read, "CASCADE_MIN_COVERAGE", 0.80)
    words, label = read.read_words("rAmogacCati", proposer)
    assert calls == want_calls and label == want_label
    assert words[-1]["surface"] == want_first


@pytest.mark.parametrize("proposer", ["byt5", "slm"])
def test_single_proposer_label_unchanged(monkeypatch, proposer) -> None:
    monkeypatch.setattr(read, "_propose", lambda t, n: (FULL, n))
    monkeypatch.setattr(read, "_assemble",
                        lambda h: [{"surface": x.surface, "verified": True} for x in h])
    assert read.read_words("rAmogacCati", proposer)[1] == proposer
