"""End-to-end verse facade: normalize -> chandas -> per-word verified analyses."""
import pytest

vidyut = pytest.importorskip("vidyut")

from sanskrit_analyzer.deep_read.kosha_engine import resolve_data_dir

pytestmark = pytest.mark.skipif(
    resolve_data_dir() is None, reason="vidyut data bundle not installed"
)

from sanskrit_analyzer.prakriya import analyze_verse


def test_devanagari_word_end_to_end():
    rec = analyze_verse("भवति")
    assert rec["input"]["slp1"] == "Bavati"
    assert rec["input"]["script"] == "devanagari"
    assert rec["padas"][0]["surface"] == "Bavati"
    top = rec["padas"][0]["analyses"][0]
    assert top["verified"] and top["lemma"] == "BU"
    assert any(s["code"] == "7.3.84" for s in top["prakriya"])


def test_verse_gets_chandas_block():
    rec = analyze_verse("kaScitkAntAvirahaguruRA svADikArapramattaH")
    assert rec["chandas"]["name"] == "mandAkrAntA"


def test_unanalyzable_word_yields_empty_analyses():
    rec = analyze_verse("xyzzyq")
    assert rec["padas"][0]["analyses"] == []


def test_json_serializable():
    import json

    json.dumps(analyze_verse("गच्छति"))
