"""SLM proposer (sanskrit_model's DCS-trained char GPT): pure parts, offline."""
from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from sanskrit_analyzer.reader.read import coverage
from sanskrit_analyzer.reader.slm import (
    CharTokenizer,
    SLMProposer,
    align,
    analysis_to_code,
    candidates,
    code_to_morph,
    derived_candidates,
    verifies,
)
from sanskrit_analyzer.reader.tags import Morph


@pytest.mark.parametrize(
    ("code", "want"),
    [
        ("c", Morph("compound_member")),
        ("u", Morph("avyaya")),
        ("a", Morph("absolutive")),
        ("t", Morph("avyaya")),                                   # infinitive
        ("n7ns", Morph("nominal", vacana="eka", vibhakti="saptamI", linga="napuMsaka")),
        ("n6s", Morph("nominal", vacana="eka", vibhakti="zazWI")),  # pronoun, no gender
        ("n1mp", Morph("nominal", vacana="bahu", vibhakti="praTamA", linga="puM")),
        ("k1nsa", Morph("participle", vacana="eka", vibhakti="praTamA", linga="napuMsaka")),
        ("k2msrP", Morph("participle", vacana="eka", vibhakti="dvitIyA", linga="puM",
                         prayoga="karmaRi")),
        ("g1ms", Morph("participle", vacana="eka", vibhakti="praTamA", linga="puM")),
        ("v3siI", Morph("verb", vacana="eka", purusha="praTama", lakaras=("laN",))),
        ("v2prM", Morph("verb", vacana="bahu", purusha="maDyama", lakaras=("low",))),
        ("v3srO", Morph("verb", vacana="eka", purusha="praTama", lakaras=("viDiliN", "ASIrliN"))),
        ("v3saI", Morph("verb", vacana="eka", purusha="praTama", lakaras=("liw", "luN", "laN"))),
        ("v2saJ", Morph("verb", vacana="eka", purusha="maDyama", lakaras=("luN", "laN"))),
        ("v3srIP", Morph("verb", vacana="eka", purusha="praTama", lakaras=("law",),
                         prayoga="karmaRi")),
        ("v1sfI", Morph("verb", vacana="eka", purusha="uttama", lakaras=("lfw", "luw"))),
        ("zz", Morph("unknown")),
        ("", Morph("unknown")),
    ],
)
def test_code_to_morph(code: str, want: Morph) -> None:
    assert code_to_morph(code) == want


def test_align_flattens_compounds_and_pairs_tags() -> None:
    hyps = align("aTa prAsAda-pfzWe paRqitaH", "aTa.u prAsAda.c pfzWa.n7ns paRqita.n1ms")
    assert [(h.surface, h.lemma, h.morph.kind) for h in hyps] == [
        ("aTa", "aTa", "avyaya"), ("prAsAda", "prAsAda", "compound_member"),
        ("pfzWe", "pfzWa", "nominal"), ("paRqitaH", "paRqita", "nominal")]


def test_align_tolerates_a_short_tag_line() -> None:
    hyps = align("aTa paRqitaH abravIt", "aTa.u paRqita.n1ms")
    assert [(h.surface, h.lemma, h.morph.kind) for h in hyps] == [
        ("aTa", "aTa", "avyaya"), ("paRqitaH", "paRqita", "nominal"),
        ("abravIt", "abravIt", "unknown")]


def test_tokenizer_longest_match_and_roundtrip(tmp_path: Path) -> None:
    stoi = {"<pad>": 0, "<bos>": 1, "<eos>": 2, "<sep>": 3, "<unk>": 4, "<dseg>": 5, "<dtag>": 6,
            "a": 7, "T": 8, ".": 9, "u": 10, " ": 11}
    p = tmp_path / "vocab.json"
    p.write_text(json.dumps(stoi))
    tok = CharTokenizer.load(p)
    ids = tok.encode("<dtag>aTa.u q")
    assert ids == [6, 7, 8, 7, 9, 10, 11, 4]
    assert tok.decode([7, 8, 7, 2, 7]) == "aTa"           # stops at <eos>


@pytest.mark.skipif(not os.environ.get("SANSKRIT_SLM_CKPT"), reason="SANSKRIT_SLM_CKPT not set")
def test_real_model_reads_a_simple_line() -> None:
    from sanskrit_analyzer.reader.slm import get_proposer

    hyps = get_proposer().propose("rAmo vanaM gacCati")
    assert [h.surface for h in hyps][-1] == "gacCati"


@pytest.mark.parametrize(
    ("surfaces", "better_than"),
    [
        (["na", "jAyate", "na", "hanyate"], ["na", "jAyate", "na"]),            # dropped word
        (["tizWa", "tvam", "svaBAvena"], ["tizWa", "tvam", "tvam", "svaBAvena"]),  # doubled word
    ],
)
def test_coverage_penalises_drops_and_duplicates(surfaces, better_than) -> None:
    def words(xs):
        return [{"surface": s} for s in xs]

    text = "".join(surfaces)
    assert coverage(text, words(surfaces)) > coverage(text, words(better_than))


@pytest.mark.parametrize(
    ("kind", "morph", "code"),
    [
        ("Subanta", "avyaya", "u"),
        ("Subanta", "puM praTamA eka", "n1ms"),
        ("Subanta", "napuMsaka saptamI eka", "n7ns"),
        ("Subanta", "strI samboDanam bahu", "n8fp"),
        ("Tinanta", "la~w kartari praTama eka", "v3srI"),
        ("Tinanta", "li~w kartari uttama bahu", "v1pa"),
        ("Tinanta", "la~w karmaRi praTama dvi", "v3drIP"),
        ("Tinanta", "lo~w kartari maDyama bahu", "v2prM"),
        ("Tinanta", "lu~N kartari praTama eka", "v3sa"),
        ("Tinanta", "la~w BAve praTama eka", None),
        ("Tinanta", "gibberish", None),
    ],
)
def test_analysis_to_code(kind: str, morph: str, code: str | None) -> None:
    assert analysis_to_code(kind, morph) == code


@pytest.mark.parametrize("surface", ["rAmaH", "gacCati", "uvAca", "aTa"])
def test_candidates_round_trip_through_verify(surface: str) -> None:
    cands = candidates(surface)
    assert cands
    for cand in cands:
        lemma, _, code = cand.rpartition(".")
        assert verifies(surface, lemma, code), cand


@pytest.mark.parametrize(
    ("surface", "lemma", "code", "want"),
    [
        ("rAmaH", "rAma", "n1ms", True),
        ("gacCati", "gam", "v3srI", True),
        ("rAmaH", "rA", "n3fd", False),       # wrong code: kosha fallback would still say verified
        ("rAmaH", "xyz", "v1pa", False),      # wrong lemma
        ("gacCati", "foo", "n3fd", False),
    ],
)
def test_verifies_has_no_catch_all(surface: str, lemma: str, code: str, want: bool) -> None:
    assert verifies(surface, lemma, code) is want


@pytest.mark.parametrize(
    ("surface", "lemma", "want_in", "want_out"),
    [
        ("gataH", "gam", "gam.k1ms", "gam.v3srI"),     # participle: no analysis_to_code shape
        ("kftvA", "kf", "kf.a", "kf.k1ms"),            # absolutive
        ("gacCati", "gam", "gam.v3srI", "gam.n1ms"),
    ],
)
def test_derived_candidates_generate_and_match(surface, lemma, want_in, want_out) -> None:
    got = derived_candidates(surface, lemma)
    assert want_in in got
    assert want_out not in got
    for cand in got:
        assert verifies(surface, lemma, cand.rpartition(".")[2], ()), cand


class _FakeScorer(SLMProposer):
    """An SLMProposer with no model: a table scorer and canned free decodes."""

    def __init__(self, scores: dict[str, float], free: str = "FREE.zz"):
        self.scores, self.calls, self.free = scores, [], free

    def score(self, prompt, chosen, candidate, final=False):
        self.calls.append((list(chosen), candidate))
        return self.scores.get(candidate, 0.0)

    def _greedy(self, prompt, chosen=None, one_word=False):
        return self.free if one_word else "greedy.line"


@pytest.mark.parametrize(
    ("padapatha", "scores", "want", "free"),
    [
        # the higher-scoring verified candidate wins, whatever the free decode says
        ("rAmaH gacCati", {"rAma.n1ms": 2.0, "ram.n1mp": 1.0, "gam.n7ns": 3.0, "gam.n7ms": 1.5},
         "rAma.n1ms gam.n7ns", "FREE.zz"),
        ("rAmaH gacCati", {"ram.n6fs": 5.0, "gam.v3srI": 1.0}, "ram.n6fs gam.v3srI", "FREE.zz"),
        # no verified candidate: free decode for that word only, the rest stay constrained
        ("rAmaH zzzq aTa", {"rAma.n1ms": 1.0}, "rAma.n1ms FREE.zz aTa.u", "FREE.zz"),
        # a compound member has no word-level derivation: decoded freely
        ("rAma-gacCati", {"gam.n7ns": 9.0}, "FREE.zz gam.n7ns", "FREE.zz"),
        # kosha has no analysis: the free decode's lemma is derived, and the best derived code wins
        ("gataH", {"gam.k1ms": 2.0, "gam.k1msP": 1.0}, "gam.k1ms", "gam.n7ns"),
        ("gataH", {"gam.k1ms": 1.0, "gam.k1msP": 2.0}, "gam.k1msP", "gam.n7ns"),
    ],
)
def test_constrained_tag_picks_best_verified_candidate(
        padapatha, scores, want, free, monkeypatch) -> None:
    from sanskrit_analyzer.reader import slm

    real = slm.candidates   # gataH is in the kosha; hide it to exercise the derive path
    monkeypatch.setattr(slm, "candidates", lambda w: () if w == "gataH" else real(w))
    fake = _FakeScorer(scores, free)
    got = fake.tag(padapatha, constrained=True)
    assert got == want
    for surface, tag in zip(padapatha.replace("-", " ").split(), got.split()):
        lemma, _, code = tag.rpartition(".")
        if lemma != "FREE":
            assert verifies(surface, lemma, code), tag
    # the scorer sees the tags already chosen for earlier words
    assert all(chosen == got.split()[:len(chosen)] for chosen, _ in fake.calls)


def test_unconstrained_tag_is_the_free_greedy_decode() -> None:
    fake = _FakeScorer({"rAma.n1ms": 9.0})
    assert fake.tag("rAmaH gacCati", constrained=False) == "greedy.line"
    assert fake.calls == []


@pytest.mark.slow
@pytest.mark.skipif(not os.environ.get("SANSKRIT_SLM_CKPT"), reason="SANSKRIT_SLM_CKPT not set")
def test_real_model_constrained_tags_are_verified() -> None:
    from sanskrit_analyzer.reader.slm import get_proposer

    tags = get_proposer().tag("rAmaH vanam gacCati", constrained=True).split()
    assert len(tags) == 3
    for surface, tag in zip(["rAmaH", "vanam", "gacCati"], tags):
        lemma, _, code = tag.rpartition(".")
        assert verifies(surface, lemma, code)
