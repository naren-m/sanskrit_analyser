"""Tests for ScriptVariants (moved from test_transliterate.py: rule 4, one
file per production module)."""

import pytest

from sanskrit_analyzer.models.scripts import Script, ScriptVariants
from tests._cases import check_cases

RAMA = ScriptVariants(devanagari="राम", iast="rāma", slp1="rAma")


def test_from_text_fills_every_script() -> None:
    cases = [
        ("explicit_devanagari", "राम", Script.DEVANAGARI),
        ("auto_detected", "राम"),
    ]

    def check(*args: object) -> None:
        variants = ScriptVariants.from_text(*args)
        assert (variants.devanagari, variants.iast, variants.slp1) == ("राम", "rāma", "rAma")

    check_cases(cases, check)


def test_get_and_str() -> None:
    cases = [
        ("devanagari", Script.DEVANAGARI, "राम"),
        ("iast", Script.IAST, "rāma"),
        ("slp1", Script.SLP1, "rAma"),
    ]

    def check(script: Script, expected: str) -> None:
        assert RAMA.get(script) == expected, RAMA.get(script)

    check_cases(cases, check)
    with pytest.raises(ValueError):
        RAMA.get(Script.HK)
    assert str(RAMA) == "राम", "str() is the Devanagari form"
    with pytest.raises(AttributeError):
        RAMA.devanagari = "सीता"  # type: ignore[misc]  # frozen
