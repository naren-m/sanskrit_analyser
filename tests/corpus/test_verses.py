"""Correctness of the three top-level interfaces on real Rāmāyaṇa and Yoga Sūtra verses.

The gold set is ``tests/data/corpus_verses.json``: eight ślokas spanning the
five kāṇḍas of the ramayanam corpus (glosses from its ``*_meaning.txt`` files)
and eight sūtras from the yoga_sutras corpus (standard padaccheda). Every case
runs through ``Analyzer.analyze``, ``DeepRead.analyze`` and
``prakriya.analyze_verse`` via :mod:`tests.corpus.engine`; the tests below
assert on the resulting reports, so a failure names the interface and the verse.

Run ``uv run python -m tests.corpus.engine`` for the full per-verse table.
"""
from __future__ import annotations

import pytest

vidyut = pytest.importorskip("vidyut")

from sanskrit_analyzer.deep_read.kosha_engine import resolve_data_dir  # noqa: E402

pytestmark = pytest.mark.skipif(
    resolve_data_dir() is None, reason="vidyut data bundle not installed"
)

from tests.corpus.engine import INTERFACES, VerseReport, load_cases, run_cases  # noqa: E402

CASES = load_cases()
IDS = [c.id for c in CASES]

# A verse counts as read when at least half its glossed words come back.
MIN_RECALL = 0.5

# Verified gaps in the library (not in the gold), keyed by root cause. Each is a
# strict xfail: a regression fails the test, and so does a fix, which is the
# signal to delete the entry. Measured 2026-09-10 (see the module docstring for
# the report command).
_GAPS: dict[str, tuple[str, list[str]]] = {
    "analyzer": (
        "Analyzer's split validator fragments real words (niyatAtmA -> niyatAt+mA, "
        "yogAnuSAsanam -> yogAn+uSA+asanam) and leaves other sandhi unsplit",
        ["bala_1.1.1", "bala_1.1.2", "bala_1.1.8", "ayodhya_2.1.1", "kishkindha_4.1.2",
         "sundara_5.1.1", "ys_1.1", "ys_1.3", "ys_1.12", "ys_2.1", "ys_2.46", "ys_3.1"],
    ),
    "prakriya": (
        "analyze_verse analyzes each whitespace pada whole: no sandhi or samAsa split, "
        "so glued words and sUtra compounds get no reading",
        ["bala_1.1.2", "kishkindha_4.1.2", "ys_1.1", "ys_1.2", "ys_1.12", "ys_2.1",
         "ys_2.46", "ys_3.1"],
    ),
    "deep_read": (
        "DeepRead leaves true samAsa whole by design (yogAnuSAsana, kriyAyoga)",
        ["ys_1.1", "ys_2.1"],
    ),
}
KNOWN_GAPS = {(cid, iface): why for iface, (why, ids) in _GAPS.items() for cid in ids}

# Analyzer emits daNDa, ASCII-colon visarga and sandhi residue ('.', '..', ':..',
# 'S', 'H', 'Fm') as word tokens on every corpus verse that carries them.
KNOWN_JUNK = {(c.id, "analyzer") for c in CASES if c.source == "ramayanam"} | {
    ("ys_1.2", "analyzer")
}


@pytest.fixture(scope="module")
def reports() -> dict[str, VerseReport]:
    return {r.case.id: r for r in run_cases(CASES)}


def _xfail(request, reason: str | None) -> None:
    if reason:
        request.node.add_marker(pytest.mark.xfail(reason=reason, strict=True))


def test_gold_covers_both_corpora():
    sources = {c.source for c in CASES}
    assert sources == {"ramayanam", "yoga_sutras"}
    assert all(c.gloss for c in CASES)


@pytest.mark.parametrize("case_id", IDS)
def test_sloka_meter(reports, case_id):
    rep = reports[case_id]
    if rep.case.meter is None:
        pytest.skip("sūtras are prose")
    assert rep.chandas is not None
    assert rep.chandas.startswith(rep.case.meter), (
        f"{rep.case.ref}: expected {rep.case.meter}, got {rep.chandas}"
    )


@pytest.mark.parametrize("case_id", IDS)
def test_prakriya_analyses_are_verified_with_trace(reports, case_id):
    rep = reports[case_id]
    for surface, analysis in rep.prakriya_analyses:
        assert analysis["verified"] is True, f"{surface}: unverified analysis"
        assert analysis["prakriya"], f"{surface}: verified but no derivation steps"


@pytest.mark.parametrize("iface", INTERFACES)
@pytest.mark.parametrize("case_id", IDS)
def test_no_junk_tokens(request, reports, case_id, iface):
    if (case_id, iface) in KNOWN_JUNK:
        _xfail(request, "Analyzer leaks punctuation and sandhi residue as tokens")
    ir = reports[case_id].interfaces[iface]
    assert not ir.junk, f"{iface} emitted non-word tokens {ir.junk} for {ir.tokens}"


@pytest.mark.parametrize("iface", INTERFACES)
@pytest.mark.parametrize("case_id", IDS)
def test_gloss_recall(request, reports, case_id, iface):
    _xfail(request, KNOWN_GAPS.get((case_id, iface)))
    ir = reports[case_id].interfaces[iface]
    missed = sorted(w for w, hit in ir.hits.items() if not hit)
    assert ir.recall >= MIN_RECALL, (
        f"{iface} recall {ir.recall:.2f} on {reports[case_id].case.ref}; "
        f"missed {missed}; produced {sorted(ir.lemmas)}"
    )
