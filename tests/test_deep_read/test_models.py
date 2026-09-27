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
from tests._cases import check_cases

_DHATU_GAM = {
    "root": "gam", "root_dev": "गम्", "gana": "BvAdi", "gana_num": 1,
    "artha_sa": "gatO", "artha_iast": "gatau", "english": "to go",
}
_UNKNOWN = {"kind": "unknown", "lemma": None, "dhatu": None, "morphology": {}}

# (row id, loader, legacy dict that must survive loader(d).to_dict() unchanged)
ROUND_TRIP_CASES = [
    ("dhatu-block", DhatuBlock.from_dict, dict(_DHATU_GAM)),
    ("analysis-without-dhatu", Analysis.from_dict,
     {"kind": "nominal", "lemma": "rAma", "dhatu": None,
      "morphology": {"vibhakti": "1", "vacana": "eka"}}),
    ("analysis-with-dhatu", Analysis.from_dict,
     {"kind": "verb", "lemma": "gam", "dhatu": dict(_DHATU_GAM),
      "morphology": {"lakara": "lat", "purusha": "prathama"}}),
    ("token-resolved", Token.from_dict,
     {"surface": "रामः", "slp1": "rAmaH", "resolved": True,
      "analyses": [{"kind": "nominal", "lemma": "rAma", "dhatu": None,
                    "morphology": {}}]}),
    ("token-preserves-reason", Token.from_dict,
     {"surface": "इक्ष्वाकुवंशप्रभवो", "slp1": "ikzvAkuvaMSapraBavo",
      "resolved": False, "analyses": [dict(_UNKNOWN)],
      "reason": "likely a compound (samāsa) or sandhi-joined padas"}),
    ("token-preserves-error-and-unknown-keys", Token.from_dict,
     {"surface": "x", "slp1": None, "resolved": False,
      "analyses": [dict(_UNKNOWN)],
      "error": "transliteration failed: boom",
      "future_key": {"nested": 1}}),
    ("full-result", DeepReadResult.from_legacy,
     {"input": "रामः", "slp1": "rAmaH", "engine": "vidyut-kosha",
      "tokens": [
          {"surface": "रामः", "slp1": "rAmaH", "resolved": True,
           "analyses": [{"kind": "nominal", "lemma": "rAma", "dhatu": None,
                         "morphology": {"vibhakti": "1"}}]},
          {"surface": "क्ष्क", "slp1": "kzka", "resolved": False,
           "analyses": [dict(_UNKNOWN)],
           "reason": "form not found in the kosha (lexicon)"},
      ],
      "notes": ["note one", "note two"]}),
    # verse_id is added downstream; it must survive the round-trip.
    ("result-forward-compat-top-level-keys", DeepReadResult.from_legacy,
     {"input": "x", "slp1": "x", "engine": "e", "tokens": [], "notes": [],
      "verse_id": "1.1.8"}),
]


def test_round_trip():
    def check(loader, legacy):
        assert loader(legacy).to_dict() == legacy

    check_cases(ROUND_TRIP_CASES, check)


def test_token_emits_reason_and_error_only_when_present():
    with_reason = dict(ROUND_TRIP_CASES[4][2])
    out = Token.from_dict(with_reason).to_dict()
    assert "reason" in out and "error" not in out

    tok = {
        "surface": "राम", "slp1": "rAma", "resolved": True,
        "analyses": [{"kind": "nominal", "lemma": "rAma", "dhatu": None,
                      "morphology": {}}],
    }
    out = Token.from_dict(tok).to_dict()
    assert "reason" not in out and "error" not in out
