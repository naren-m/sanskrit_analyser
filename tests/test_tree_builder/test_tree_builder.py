"""Tests for parse tree builder."""

import asyncio

import pytest

from sanskrit_analyzer.engines.base import EngineResult, Segment
from sanskrit_analyzer.engines.runner import AnalyzedSegment, EngineRunResult
from sanskrit_analyzer.engines.vidyut_engine import VidyutEngine
from sanskrit_analyzer.models.morphology import (
    Case,
    Gender,
    MorphologicalTag,
    Number,
    PartOfSpeech,
    Person,
    Tense,
    Voice,
)
from sanskrit_analyzer.models.tree import CacheTier
from sanskrit_analyzer.tree_builder import TreeBuilder, TreeBuilderConfig
from tests._cases import check_cases


def _run_result() -> EngineRunResult:
    """rāmaḥ gacchati as two engines would agree on it."""
    return EngineRunResult(
        segments=[
            AnalyzedSegment(
                surface="rAmaH",
                lemma="rAma",
                morphology="noun.masculine.singular.nominative",
                confidence=0.9,
                pos="noun",
                meanings=["Rama", "pleasing"],
                engine_votes={"vidyut": 0.9, "local_byt5": 0.85},
                agreement_score=0.9,
            ),
            AnalyzedSegment(
                surface="gacCati",
                lemma="gam",
                morphology="verb.third.singular.present.active",
                confidence=0.95,
                pos="verb",
                meanings=["goes", "walks"],
                engine_votes={"vidyut": 0.95, "local_byt5": 0.92},
                agreement_score=0.95,
            ),
        ],
        engine_results={
            "vidyut": EngineResult(
                engine="vidyut",
                segments=[
                    Segment(surface="rAmaH", lemma="rAma", confidence=0.9, pos="noun"),
                    Segment(surface="gacCati", lemma="gam", confidence=0.95, pos="verb"),
                ],
                confidence=0.92,
            ),
            "local_byt5": EngineResult(
                engine="local_byt5",
                segments=[
                    Segment(surface="rAmaH", lemma="rAma", confidence=0.85, pos="noun"),
                    Segment(surface="gacCati", lemma="gam", confidence=0.92, pos="verb"),
                ],
                confidence=0.88,
            ),
        },
        overall_confidence=0.9,
    )


def _single(segment: AnalyzedSegment) -> EngineRunResult:
    return EngineRunResult(segments=[segment], engine_results={}, overall_confidence=0.9)


def _word(tree, group=0):
    return tree.best_parse.sandhi_groups[group].base_words[0]


# Built from _run_result() with the default config and mode="educational".
# (id, probe on the tree, expected value)
TREE_CASES = [
    ("sentence id is prefixed sent_", lambda t: t.sentence_id.startswith("sent_"), True),
    ("original text kept", lambda t: t.original_text, "rāmaḥ gacchati"),
    ("normalized SLP1 kept", lambda t: t.normalized_slp1, "rAmaH gacCati"),
    ("one parse in the forest", lambda t: len(t.parse_forest), 1),
    ("overall confidence from the run", lambda t: t.confidence.overall, 0.9),
    ("mode preserved", lambda t: t.mode, "educational"),
    ("cache tier defaults to NONE", lambda t: t.cached_at, CacheTier.NONE),
    ("parse id is prefixed parse_", lambda t: t.best_parse.parse_id.startswith("parse_"), True),
    ("one sandhi group per segment", lambda t: len(t.best_parse.sandhi_groups), 2),
    ("parse word count", lambda t: t.best_parse.word_count, 2),
    (
        "both engines' votes reach the parse",
        lambda t: set(t.best_parse.engine_votes) >= {"vidyut", "local_byt5"},
        True,
    ),
    ("group surface form", lambda t: t.best_parse.sandhi_groups[0].surface_form, "rAmaH"),
    ("group word count", lambda t: t.best_parse.sandhi_groups[0].word_count, 1),
    ("group is a single word", lambda t: t.best_parse.sandhi_groups[0].is_single_word, True),
    ("word lemma", lambda t: _word(t).lemma, "rAma"),
    ("word surface form", lambda t: _word(t).surface_form, "rAmaH"),
    ("word SLP1 script is the lemma", lambda t: _word(t).scripts.slp1, "rAma"),
    ("word meanings kept", lambda t: len(_word(t).meanings), 2),
    ("tree SLP1 script", lambda t: t.scripts.slp1, "rAmaH gacCati"),
    ("tree Devanagari variant generated", lambda t: t.scripts.devanagari is not None, True),
    ("tree IAST variant generated", lambda t: t.scripts.iast is not None, True),
    ("all_words[0] SLP1 script", lambda t: t.all_words[0].scripts.slp1, "rAma"),
    (
        "noun morphology string parsed into a tag",
        lambda t: (
            _word(t).morphology.pos,
            _word(t).morphology.gender,
            _word(t).morphology.number,
            _word(t).morphology.case,
        ),
        (PartOfSpeech.NOUN, Gender.MASCULINE, Number.SINGULAR, Case.NOMINATIVE),
    ),
    ("verb lemma", lambda t: _word(t, 1).lemma, "gam"),
    ("verb is marked verb-derived", lambda t: _word(t, 1).is_verb_derived, True),
    ("verb dhatu looked up", lambda t: _word(t, 1).dhatu.dhatu, "gam"),
    (
        "to_dict carries top-level keys",
        lambda t: {"sentence_id", "original_text", "parse_forest"} <= set(t.to_dict()),
        True,
    ),
    ("to_dict carries the parse", lambda t: len(t.to_dict()["parse_forest"]), 1),
    (
        "to_dict parse carries id and groups",
        lambda t: {"parse_id", "sandhi_groups"} <= set(t.to_dict()["parse_forest"][0]),
        True,
    ),
]

# (id, config, segment, probe on the only word, expected)
CONFIG_CASES = [
    (
        "lookup_dhatus=False leaves the verb without a dhatu",
        TreeBuilderConfig(lookup_dhatus=False),
        AnalyzedSegment(
            surface="gacCati",
            lemma="gam",
            morphology="verb.third.singular.present",
            confidence=0.9,
            pos="verb",
            engine_votes={"test": 0.9},
            agreement_score=0.9,
        ),
        lambda w: w.dhatu,
        None,
    ),
    (
        "generate_meanings=False drops engine meanings",
        TreeBuilderConfig(generate_meanings=False),
        AnalyzedSegment(
            surface="rAmaH",
            lemma="rAma",
            confidence=0.9,
            pos="noun",
            meanings=["Rama", "pleasing"],
            engine_votes={"test": 0.9},
            agreement_score=0.9,
        ),
        lambda w: len(w.meanings),
        0,
    ),
]

# (id, morphology string, pos, expected fields or None for "no tag")
MORPHOLOGY_CASES = [
    (
        "english-noun",
        "noun.masculine.singular.nominative",
        "noun",
        {
            "pos": PartOfSpeech.NOUN,
            "gender": Gender.MASCULINE,
            "number": Number.SINGULAR,
            "case": Case.NOMINATIVE,
        },
    ),
    (
        "abbreviated-noun",
        "mas.sg.nom",
        "noun",
        {"gender": Gender.MASCULINE, "number": Number.SINGULAR, "case": Case.NOMINATIVE},
    ),
    (
        "english-verb",
        "third.singular.present.active",
        "verb",
        {
            "pos": PartOfSpeech.VERB,
            "person": Person.THIRD,
            "number": Number.SINGULAR,
            "tense": Tense.PRESENT,
            "voice": Voice.ACTIVE,
        },
    ),
    # Exactly what VidyutEngine emits. Before it emitted "tinanta.si.thi.lat"
    # and the parser returned None for every word Analyzer.analyze produced.
    (
        "vidyut-subanta",
        "noun.masculine.dative.singular",
        "noun",
        {"gender": Gender.MASCULINE, "case": Case.DATIVE, "number": Number.SINGULAR},
    ),
    (
        "vidyut-tinanta",
        "verb.third.singular.imperfect.active",
        "verb",
        {"person": Person.THIRD, "tense": Tense.IMPERFECT, "voice": Voice.ACTIVE},
    ),
    (
        "vidyut-pos-name",
        "masculine.accusative.plural",
        "subanta",
        {"pos": PartOfSpeech.NOUN, "case": Case.ACCUSATIVE, "number": Number.PLURAL},
    ),
    # Substring matching once read "nom" as masculine ("m") and any "du" as dual.
    (
        "no-substring-hits",
        "feminine.nominative.singular",
        "noun",
        {"gender": Gender.FEMININE, "number": Number.SINGULAR},
    ),
    ("verb-has-no-case", "verb.third.dual.locative", "verb", {"case": None, "number": Number.DUAL}),
    ("neuter", "neuter", "noun", {"gender": Gender.NEUTER}),
    ("no-pos", "masculine.singular", None, None),
    ("unknown-pos", "masculine.singular", "xyz", None),
]

# (id, root, expected (dhatu, gana, meaning substring) or None)
DHATU_CASES = [
    ("common root gam is found with its meaning", "gam", ("gam", None, "to go")),
    ("kṛ is class 8", "kf", (None, 8, None)),
    ("unknown root returns None", "unknown_root", None),
]

# (id, pos string, morphology tag, is verb)
IS_VERB_CASES = [
    ("verb pos with verb tag", "verb", MorphologicalTag(pos=PartOfSpeech.VERB), True),
    ("verb pos with no tag", "verb", None, True),
    ("noun pos with noun tag", "noun", MorphologicalTag(pos=PartOfSpeech.NOUN), False),
    ("no pos, no tag", None, None, False),
]


def test_build_tree() -> None:
    config = TreeBuilderConfig()
    # Defaults: every enrichment is on unless a caller opts out.
    assert (config.lookup_dhatus, config.generate_meanings, config.infer_compounds) == (
        True,
        True,
        True,
    )
    tree = TreeBuilder().build(
        _run_result(),
        original_text="rāmaḥ gacchati",
        normalized_slp1="rAmaH gacCati",
        mode="educational",
    )

    def check(probe, expected):
        got = probe(tree)
        assert got == expected, f"got {got!r}, want {expected!r}"

    check_cases(TREE_CASES, check)


def test_build_edge_inputs() -> None:
    builder = TreeBuilder()

    # Raw engine segments: one engine means full agreement.
    tree = builder.build_from_segments(
        [
            Segment(
                surface="vanam",
                lemma="vana",
                morphology="noun.neuter.singular.accusative",
                confidence=0.85,
                pos="noun",
                meanings=["forest"],
            )
        ],
        original_text="vanam",
        normalized_slp1="vanam",
        engine_name="test_engine",
    )
    assert len(tree.parse_forest) == 1
    assert tree.confidence.engine_agreement == 1.0
    assert tree.all_words[0].lemma == "vana"

    # No segments: empty forest, no best parse.
    empty = builder.build(
        EngineRunResult(segments=[], engine_results={}, overall_confidence=0.0),
        original_text="",
        normalized_slp1="",
    )
    assert len(empty.parse_forest) == 0
    assert empty.best_parse is None

    # Identical input twice: sentence and parse IDs share a prefix but differ.
    seg = AnalyzedSegment(
        surface="test",
        lemma="test",
        confidence=0.9,
        engine_votes={"test": 0.9},
        agreement_score=0.9,
    )
    tree1 = builder.build(_single(seg), "test", "test")
    tree2 = builder.build(_single(seg), "test", "test")
    assert tree1.sentence_id.startswith("sent_")
    assert tree2.sentence_id.startswith("sent_")
    assert tree1.sentence_id != tree2.sentence_id
    if tree1.best_parse and tree2.best_parse:
        assert tree1.best_parse.parse_id != tree2.best_parse.parse_id


def test_config_switches() -> None:
    def check(config, segment, probe, expected):
        tree = TreeBuilder(config).build(_single(segment), "x", segment.surface)
        assert probe(tree.all_words[0]) == expected

    check_cases(CONFIG_CASES, check)


def test_parse_morphology() -> None:
    builder = TreeBuilder()

    def check(morph_str, pos, expected):
        tag = builder._parse_morphology(morph_str, pos)
        if expected is None:
            assert tag is None, f"expected None, got {tag}"
            return
        assert tag is not None
        for field, want in expected.items():
            assert getattr(tag, field) == want, f"{field}={getattr(tag, field)} want {want}"

    check_cases(MORPHOLOGY_CASES, check)


def test_vidyut_output_reaches_the_tree() -> None:
    """End to end through the real engine: every word must carry morphology."""
    engine = VidyutEngine()
    if not engine._available:
        pytest.skip("vidyut data not available")
    result = asyncio.run(engine.analyze("devAya aBavat"))
    builder = TreeBuilder()
    tags = [builder._parse_morphology(s.morphology, s.pos) for s in result.segments]
    assert tags[0] is not None and tags[0].case == Case.DATIVE
    assert tags[1] is not None and tags[1].tense == Tense.IMPERFECT


def test_dhatu_lookup_and_verb_detection() -> None:
    builder = TreeBuilder()

    def check_dhatu(root, expected):
        dhatu = builder._lookup_dhatu(root)
        if expected is None:
            assert dhatu is None
            return
        name, gana, meaning = expected
        assert dhatu is not None
        if name is not None:
            assert dhatu.dhatu == name
        if gana is not None:
            assert dhatu.gana == gana
        if meaning is not None:
            assert meaning in dhatu.meanings

    def check_is_verb(pos, morph, expected):
        assert builder._is_verb(pos, morph) is expected

    check_cases(DHATU_CASES, check_dhatu)
    check_cases(IS_VERB_CASES, check_is_verb)
