"""Meter identification on one real Rāmāyaṇa verse per meter the library knows.

Gold is ``tests/data/corpus_meters.json``. The verses were found by scanning
all 21,568 lines of the ramayanam corpus with the chandas identifier and then
checking each candidate's four pāda scans against the gaṇa formula in
``data/meters-full.csv`` (the ardhasama pairs against their odd/even halves).
Every meter Vālmīki uses that vidyut can name is here, plus the three śloka
forms not already covered by ``corpus_verses.json``. Verses go through
``analyze_verse``, the same entry point downstream consumers call.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

vidyut = pytest.importorskip("vidyut")

from sanskrit_analyzer.deep_read.kosha_engine import resolve_data_dir  # noqa: E402
from sanskrit_analyzer.prakriya import analyze_verse  # noqa: E402

pytestmark = pytest.mark.skipif(
    resolve_data_dir() is None, reason="vidyut data bundle not installed"
)

GOLD = Path(__file__).resolve().parents[1] / "data" / "corpus_meters.json"
CASES = json.loads(GOLD.read_text())

# Verified gaps, strict: delete the entry when the identifier learns the meter.
KNOWN_GAPS = {
    "upajati_3.23.32": "vidyut has no upajAti entry; 506 corpus verses whose pādas "
    "freely mix indravajrA and upendravajrA come back unnamed",
}


@pytest.mark.parametrize("case", CASES, ids=[c["id"] for c in CASES])
def test_meter_identified(request, case):
    if case["id"] in KNOWN_GAPS:
        request.node.add_marker(pytest.mark.xfail(reason=KNOWN_GAPS[case["id"]], strict=True))
    chandas = analyze_verse(case["text"])["chandas"]
    got = chandas["name"] if chandas else None
    assert got == case["meter"], f"{case['ref']}: expected {case['meter']}, got {got}"


def test_gold_covers_every_meter_valmiki_uses():
    meters = {c["meter"].split(" ")[0] for c in CASES}
    assert len(meters) >= 15
    assert "anuzwuB" in meters
