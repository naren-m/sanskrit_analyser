"""Analysis-by-synthesis: kosha lookup verified by forward generation."""
import pytest

vidyut = pytest.importorskip("vidyut")

from sanskrit_analyzer.deep_read.kosha_engine import resolve_data_dir

pytestmark = pytest.mark.skipif(
    resolve_data_dir() is None, reason="vidyut data bundle not installed"
)

from sanskrit_analyzer.prakriya.analyzer import analyze_pada


def test_bhavati_verified_with_trace():
    analyses = analyze_pada("Bavati")
    assert analyses, "Bavati must yield at least one verified analysis"
    a = analyses[0]
    assert a.verified is True
    assert a.lemma == "BU"
    codes = [s.code for s in a.prakriya]
    assert "3.4.78" in codes       # tiptasJi... (tiN assignment)
    assert "7.3.84" in codes       # sārvadhātukārdhadhātukayoḥ (guṇa)
    guna = next(s for s in a.prakriya if s.code == "7.3.84")
    assert guna.sutra_text and "sArvaDAtukA" in guna.sutra_text
    # the final step still shows morpheme boundaries; joined it is the surface
    assert a.prakriya[-1].form.replace(" + ", "") == "Bavati"


def test_final_visarga_form_resolves_via_desandhi():
    # kosha keys pausal -H forms as -s; desandhi_candidates bridges that.
    analyses = analyze_pada("rAmaH")
    assert any(a.lemma == "rAma" for a in analyses)


def test_gibberish_returns_empty_never_fabricates():
    assert analyze_pada("xyzzyq") == []


def test_dedup_and_limit():
    analyses = analyze_pada("Bavati", limit=3)
    assert len(analyses) <= 3
    keys = [(a.kind, a.lemma, a.morph) for a in analyses]
    assert len(keys) == len(set(keys))


def test_to_dict_roundtrip():
    a = analyze_pada("gacCati")[0]
    d = a.to_dict()
    assert d["lemma"] == "gam"
    assert d["prakriya"][0]["code"]
