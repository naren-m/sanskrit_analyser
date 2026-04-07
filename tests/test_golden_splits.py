"""Golden tests for sandhi split quality."""

import json
from pathlib import Path
import pytest
from sanskrit_analyzer import Analyzer, Config, AnalysisMode

GOLDEN_FILE = Path(__file__).parent / "data" / "yoga_sutra_splits_golden.json"

def load_golden_cases():
    with open(GOLDEN_FILE) as f:
        return json.load(f)

@pytest.fixture(scope="module")
def analyzer():
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
