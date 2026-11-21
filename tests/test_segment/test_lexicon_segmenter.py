"""LexiconSegmenter: verbatim and junction edges, OOV, ordering, pruning."""

import pytest

from sanskrit_analyzer.segment import LexiconSegmenter, pausa

LEXICON = {"tataH": 100, "rAmaH": 100, "asti": 50}


@pytest.mark.parametrize(
    ("lexicon", "src", "kwargs", "expected_top"),
    [
        pytest.param(LEXICON, "tataHrAmaH", {}, ["tataH", "rAmaH"], id="verbatim"),
        pytest.param(LEXICON, "rAmo'sti", {}, ["rAmaH", "asti"], id="junction"),
        pytest.param(LEXICON, "qqqqxxxxzzzz", {}, None, id="oov-empty"),
        pytest.param(
            LEXICON, "tataHqq", {"oov_penalty": -5.0}, ["tataH", "qq"], id="oov-penalty"
        ),
        # rare 10-char entry that splits into two frequent padas is dropped
        pytest.param({**LEXICON, "tataHrAmaH": 5}, "tataHrAmaH", {},
                     ["tataH", "rAmaH"], id="span-pruned"),
    ],
)
def test_kbest_top(lexicon, src, kwargs, expected_top):
    out = LexiconSegmenter(lexicon).kbest(src, **kwargs)
    assert (out[0][1] if out else None) == expected_top


def test_span_kept_without_pruning():
    lex = {**LEXICON, "tataHrAmaH": 5}
    out = LexiconSegmenter(lex, prune_spans=None).kbest("tataHrAmaH")
    assert ["tataHrAmaH"] in [p for _, p in out]


def test_scores_descend_and_ties_by_text():
    out = LexiconSegmenter({**LEXICON, "tataHrAmaH": 5}, prune_spans=None).kbest("tataHrAmaH")
    assert len(out) >= 2
    scores = [sc for sc, _ in out]
    assert scores == sorted(scores, reverse=True)


def test_pausa():
    assert pausa("rAmas") == "rAmaH"
    assert pausa("rAma") == "rAma"
