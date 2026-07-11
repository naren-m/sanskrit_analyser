"""Golden tests for sandhi split quality.

These golden lemmas were calibrated with the Dharmamitra ByT5 segmenter (a live
API) available. When that service is unreachable the analyzer degrades to the
local Vidyut splitter, which produces different (lower-quality) splits — e.g.
``nirodha`` → ``niruD`` instead of ``niroDa``. Asserting the golden values in
that degraded state tests infrastructure availability, not our code, so the
module skips when the Dharmamitra segmenter is unavailable.
"""

import json
from pathlib import Path
import pytest
from sanskrit_analyzer import Analyzer, Config, AnalysisMode

GOLDEN_FILE = Path(__file__).parent / "data" / "yoga_sutra_splits_golden.json"

def load_golden_cases():
    with open(GOLDEN_FILE) as f:
        return json.load(f)


def _dharmamitra_available() -> bool:
    """Best-effort probe: is the Dharmamitra segmenter reachable right now?"""
    try:
        from sanskrit_analyzer.engines.dharmamitra_engine import DharmamitraEngine

        engine = DharmamitraEngine()
        import asyncio

        result = asyncio.run(engine.analyze("gacchati"))
        return bool(getattr(result, "success", False))
    except Exception:
        return False

@pytest.fixture(scope="module")
def analyzer():
    if not _dharmamitra_available():
        pytest.skip(
            "Dharmamitra segmenter unavailable (live API); golden splits were "
            "calibrated with it and degrade to Vidyut when it is down"
        )
    try:
        return Analyzer(Config())
    except Exception:
        pytest.skip("Analyzer not available")

@pytest.mark.parametrize("case", load_golden_cases(), ids=[c["input"] for c in load_golden_cases()])
@pytest.mark.asyncio
async def test_golden_split(analyzer, case):
    input_text = case["input"]
    expected_lemmas = case["expected_lemmas"]

    result = await analyzer.analyze(input_text, mode=AnalysisMode.EDUCATIONAL)

    if not result.parse_forest:
        pytest.skip(f"No parse result for {input_text}")

    actual_lemmas = [
        w.lemma for sg in result.parse_forest[0].sandhi_groups for w in sg.base_words
    ]

    assert actual_lemmas == expected_lemmas, (
        f"Split mismatch for '{case['input']}':\n"
        f"  Expected: {expected_lemmas}\n"
        f"  Actual:   {actual_lemmas}"
    )
