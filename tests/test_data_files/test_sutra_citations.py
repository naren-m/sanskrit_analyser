"""Every sūtra number cited in the bundled grammar YAML must be a real sūtra.

The reference is the Aṣṭādhyāyī text shipped in the vidyut data bundle. This
guards against the earlier state of ``sutras.yaml``, where most numbers were
invented and pointed at unrelated rules.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from indic_transliteration import sanscript

from sanskrit_analyzer.prakriya import sutra_index

DATA = Path(__file__).resolve().parents[2] / "sanskrit_analyzer" / "data"

pytestmark = pytest.mark.skipif(
    not sutra_index.resolve_data_dir(), reason="vidyut data bundle not available"
)


@pytest.fixture(scope="module")
def index() -> sutra_index.SutraIndex:
    return sutra_index.get_index()


def _load(name: str) -> dict:
    with (DATA / name).open(encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def _rules(name: str) -> list[tuple[str, dict]]:
    """``(label, rule)`` for every rule in a ``categories``-keyed grammar YAML."""
    return [
        (f"{category}/{rule['name']}", rule)
        for category, rules in _load(name)["categories"].items()
        for rule in rules
    ]


def _slp1(devanagari: str) -> str:
    """Devanāgarī -> SLP1, spaces dropped so only the akṣaras are compared."""
    slp1 = sanscript.transliterate(devanagari, sanscript.DEVANAGARI, sanscript.SLP1)
    return slp1.replace(" ", "")


@pytest.mark.parametrize(
    "label,code", [(label, r["sutra"]) for label, r in _rules("pratyayas.yaml")]
)
def test_pratyaya_cites_real_sutra(index, label, code):
    assert index.lookup(code) is not None, f"{label}: no sūtra {code}"


@pytest.mark.parametrize(
    "label,code,text",
    [(label, r["sutra"], r["rule"]) for label, r in _rules("sandhi_rules.yaml")],
)
def test_sandhi_rule_matches_sutra(index, label, code, text):
    real = index.lookup(code)
    assert real is not None, f"{label}: no sūtra {code}"
    assert _slp1(text) == real.text.replace(" ", ""), (
        f"{label}: {code} reads {real.text!r}, yaml says {text!r}"
    )


def _sutra_entries() -> list[tuple[str, str]]:
    return [
        (f"{adhyaya}.{pada}.{entry['number']}", entry["text"])
        for adhyaya, ad in _load("sutras.yaml")["adhyayas"].items()
        for pada, entries in ad["padas"].items()
        for entry in entries
    ]


@pytest.mark.parametrize("code,text", _sutra_entries())
def test_sutras_yaml_number_matches_text(index, code, text):
    real = index.lookup(code)
    assert real is not None, f"no sūtra {code}"
    assert _slp1(text) == real.text.replace(" ", ""), f"{code} is {real.text!r}, yaml has {text!r}"
