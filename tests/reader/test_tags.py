"""ByT5 SLM tag decoding. Rows are real model outputs on known forms."""
from __future__ import annotations

import pytest

from sanskrit_analyzer.reader.tags import Morph, decode


@pytest.mark.parametrize(
    ("tag", "want"),
    [
        # nominals: number + case + gender
        ("SNM", Morph("nominal", vacana="eka", vibhakti="praTamA", linga="puM")),
        ("PLNe", Morph("nominal", vacana="bahu", vibhakti="saptamI", linga="napuMsaka")),
        ("SIM", Morph("nominal", vacana="eka", vibhakti="tftIyA", linga="puM")),
        ("PDM", Morph("nominal", vacana="bahu", vibhakti="caturTI", linga="puM")),
        ("SNF", Morph("nominal", vacana="eka", vibhakti="praTamA", linga="strI")),
        ("SG", Morph("nominal", vacana="eka", vibhakti="zazWI")),            # 2nd-person pronoun
        ("DuNM", Morph("nominal", vacana="dvi", vibhakti="praTamA", linga="puM")),
        # finite verbs: number + tense + person + mood (or number + person + tense + mood)
        ("SPr3In", Morph("verb", vacana="eka", purusha="praTama", lakaras=("law",))),
        ("SPr3Im", Morph("verb", vacana="eka", purusha="praTama", lakaras=("low",))),
        ("SPr3O", Morph("verb", vacana="eka", purusha="praTama", lakaras=("viDiliN", "ASIrliN"))),
        ("SFu1In", Morph("verb", vacana="eka", purusha="uttama", lakaras=("lfw", "luw"))),
        ("SPs3In", Morph("verb", vacana="eka", purusha="praTama", lakaras=("laN", "liw", "luN"))),
        ("SPs2", Morph("verb", vacana="eka", purusha="maDyama", lakaras=("laN", "liw", "luN"))),
        ("S2ImIn", Morph("verb", vacana="eka", purusha="maDyama", lakaras=("laN",))),
        ("DuPr2In", Morph("verb", vacana="dvi", purusha="maDyama", lakaras=("law",))),
        # participle, indeclinable, absolutive, compound member
        ("SNPaPsNe", Morph("participle", vacana="eka", vibhakti="praTamA", linga="napuMsaka")),
        ("U", Morph("avyaya")),
        ("Co", Morph("absolutive")),
        ("Cp", Morph("compound_member")),
        # voice / formation suffixes seen on Rāmāyaṇa verses
        ("SPr3InPv", Morph("verb", vacana="eka", purusha="praTama", lakaras=("law",),
                           prayoga="karmaRi")),
        ("SPs3InPe", Morph("verb", vacana="eka", purusha="praTama", lakaras=("liw",))),
        ("SPs3InTh", Morph("verb", vacana="eka", purusha="praTama", lakaras=("laN", "liw", "luN"))),
        ("SAPaPrNePv", Morph("participle", vacana="eka", vibhakti="dvitIyA", linga="napuMsaka",
                             prayoga="karmaRi")),
        ("DuAPaPrMPv", Morph("participle", vacana="dvi", vibhakti="dvitIyA", linga="puM",
                             prayoga="karmaRi")),
        ("PaCp", Morph("compound_member")),
        ("SBNe", Morph("nominal", vacana="eka", vibhakti="paYcamI", linga="napuMsaka")),
        ("SINeGd", Morph("participle", vacana="eka", vibhakti="tftIyA", linga="napuMsaka")),
        ("", Morph("unknown")),
        ("XYZ", Morph("unknown")),
    ],
)
def test_decode(tag: str, want: Morph) -> None:
    assert decode(tag) == want
