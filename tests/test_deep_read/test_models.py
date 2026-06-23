"""Round-trip tests for the typed Deep Read result model.

The promotion's behavior-preservation guarantee is::

    DeepReadResult.from_legacy(d).to_dict() == d

These tests pin that invariant field-for-field, including the optional
``reason`` / ``error`` token keys and forward-compatible extras.
"""

from sanskrit_analyzer.deep_read.models import (
    Analysis,
    DeepReadResult,
    DhatuBlock,
    Token,
)


def test_dhatu_block_round_trip():
    d = {
        "root": "gam", "root_dev": "गम्", "gana": "BvAdi", "gana_num": 1,
        "artha_sa": "gatO", "artha_iast": "gatau", "english": "to go",
    }
    assert DhatuBlock.from_dict(d).to_dict() == d


def test_analysis_round_trip_with_and_without_dhatu():
    nominal = {"kind": "nominal", "lemma": "rAma", "dhatu": None,
               "morphology": {"vibhakti": "1", "vacana": "eka"}}
    assert Analysis.from_dict(nominal).to_dict() == nominal

    verb = {
        "kind": "verb", "lemma": "gam",
        "dhatu": {"root": "gam", "root_dev": "गम्", "gana": "BvAdi",
                  "gana_num": 1, "artha_sa": "gatO", "artha_iast": "gatau",
                  "english": "to go"},
        "morphology": {"lakara": "lat", "purusha": "prathama"},
    }
    assert Analysis.from_dict(verb).to_dict() == verb


def test_token_round_trip_resolved():
    tok = {
        "surface": "रामः", "slp1": "rAmaH", "resolved": True,
        "analyses": [{"kind": "nominal", "lemma": "rAma", "dhatu": None,
                      "morphology": {}}],
    }
    assert Token.from_dict(tok).to_dict() == tok


def test_token_round_trip_preserves_reason():
    tok = {
        "surface": "इक्ष्वाकुवंशप्रभवो", "slp1": "ikzvAkuvaMSapraBavo",
        "resolved": False,
        "analyses": [{"kind": "unknown", "lemma": None, "dhatu": None,
                      "morphology": {}}],
        "reason": "likely a compound (samāsa) or sandhi-joined padas",
    }
    out = Token.from_dict(tok).to_dict()
    assert out == tok
    assert "reason" in out and "error" not in out


def test_token_round_trip_preserves_error_and_unknown_keys():
    tok = {
        "surface": "x", "slp1": None, "resolved": False,
        "analyses": [{"kind": "unknown", "lemma": None, "dhatu": None,
                      "morphology": {}}],
        "error": "transliteration failed: boom",
        "future_key": {"nested": 1},
    }
    assert Token.from_dict(tok).to_dict() == tok


def test_token_omits_reason_and_error_when_absent():
    tok = {
        "surface": "राम", "slp1": "rAma", "resolved": True,
        "analyses": [{"kind": "nominal", "lemma": "rAma", "dhatu": None,
                      "morphology": {}}],
    }
    out = Token.from_dict(tok).to_dict()
    assert "reason" not in out and "error" not in out


def test_full_result_round_trip():
    legacy = {
        "input": "रामः", "slp1": "rAmaH", "engine": "vidyut-kosha",
        "tokens": [
            {"surface": "रामः", "slp1": "rAmaH", "resolved": True,
             "analyses": [{"kind": "nominal", "lemma": "rAma", "dhatu": None,
                           "morphology": {"vibhakti": "1"}}]},
            {"surface": "क्ष्क", "slp1": "kzka", "resolved": False,
             "analyses": [{"kind": "unknown", "lemma": None, "dhatu": None,
                           "morphology": {}}],
             "reason": "form not found in the kosha (lexicon)"},
        ],
        "notes": ["note one", "note two"],
    }
    assert DeepReadResult.from_legacy(legacy).to_dict() == legacy


def test_result_preserves_forward_compat_top_level_keys():
    legacy = {
        "input": "x", "slp1": "x", "engine": "e", "tokens": [], "notes": [],
        "verse_id": "1.1.8",  # added downstream; must survive round-trip
    }
    assert DeepReadResult.from_legacy(legacy).to_dict() == legacy
