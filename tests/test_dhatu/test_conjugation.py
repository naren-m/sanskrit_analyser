"""Conjugation: forms are derived by vidyut, not read from a table."""

import pytest

from sanskrit_analyzer.dhatu import conjugation

pytestmark = pytest.mark.skipif(
    not conjugation.is_available(), reason="vidyut data bundle not available"
)


def test_lat_paradigm():
    rows = conjugation.conjugate("01.1137", "lat")
    forms = {(r["purusha"], r["vacana"]): r["forms_iast"] for r in rows}
    assert forms[("prathama", "eka")] == ["gacchati"]
    assert forms[("madhyama", "dvi")] == ["gacchathaḥ"]
    assert forms[("uttama", "bahu")] == ["gacchāmaḥ"]


def test_pada_is_derived_not_assumed():
    """√gam is parasmaipada only; √nah forms both."""
    assert conjugation.padas_for("01.1137") == ["parasmaipada"]
    assert conjugation.padas_for("04.0062") == ["parasmaipada", "ātmanepada"]


def test_every_lakara_derives():
    for lakara in conjugation.LAKARA_NAMES:
        assert conjugation.conjugate("01.1137", lakara), lakara


def test_lakara_names_and_unknown_inputs():
    assert conjugation.normalize_lakara("lin") == "vidhilin"
    assert conjugation.normalize_lakara("nope") is None
    with pytest.raises(KeyError):
        conjugation.conjugate("01.1137", "nope")
    with pytest.raises(KeyError):
        conjugation.conjugate("99.9999", "lat")
