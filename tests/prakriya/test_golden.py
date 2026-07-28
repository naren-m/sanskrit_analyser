"""Golden verse: BG 2.47 pāda a — hand-verified expectations (design doc §5)."""
import pytest

vidyut = pytest.importorskip("vidyut")

from sanskrit_analyzer.deep_read.kosha_engine import resolve_data_dir

pytestmark = pytest.mark.skipif(
    resolve_data_dir() is None, reason="vidyut data bundle not installed"
)

from sanskrit_analyzer.prakriya import analyze_verse

BG_2_47_A = "कर्मण्येवाधिकारस्ते मा फलेषु कदाचन"


def test_bg_2_47_structure():
    rec = analyze_verse(BG_2_47_A)
    surfaces = [p["surface"] for p in rec["padas"]]
    assert "Palezu" in surfaces
    phalesu = next(p for p in rec["padas"] if p["surface"] == "Palezu")
    assert any(
        a["lemma"] == "Pala" and a["verified"] for a in phalesu["analyses"]
    ), "Palezu must verify as saptamī bahuvacana of Pala"


def test_every_verified_analysis_has_cited_trace():
    rec = analyze_verse(BG_2_47_A)
    for pada in rec["padas"]:
        for a in pada["analyses"]:
            assert a["verified"]
            assert a["prakriya"], f"verified analysis of {pada['surface']} lacks trace"
            assert all(s["code"] for s in a["prakriya"])
