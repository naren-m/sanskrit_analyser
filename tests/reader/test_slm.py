"""SLM proposer (sanskrit_model's DCS-trained char GPT): pure parts, offline."""
from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from sanskrit_analyzer.reader.read import coverage
from sanskrit_analyzer.reader.slm import CharTokenizer, align, code_to_morph
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
