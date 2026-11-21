"""Cross-validate the default chandas engine against vidyut.chandas.

vidyut ships its own meter table, so over the golden set it is a second opinion
that shares no code with the ported engine. Skips when vidyut or its data bundle
is unavailable (the default engine itself never needs them).
"""
import json
from pathlib import Path

import pytest

pytest.importorskip("vidyut")

from sanskrit_analyzer.models.scripts import Script  # noqa: E402
from sanskrit_analyzer.prakriya import chandas  # noqa: E402
from sanskrit_analyzer.utils.transliterate import to_slp1  # noqa: E402
from sanskrit_analyzer.vidyut_data import resolve_data_dir  # noqa: E402

pytestmark = pytest.mark.skipif(
    resolve_data_dir() is None, reason="vidyut data bundle not installed"
)

GOLDEN_PATH = Path(__file__).resolve().parents[1] / "data" / "golden_meters.json"
GOLDEN = json.loads(GOLDEN_PATH.read_text())

#: Verses where vidyut names a different meter than the engine, with the reason.
#: Kumarasambhava 1.1 mixes indravajrā/upendravajrā per pāda; vidyut reads the
#: alternation as the ardhasama row ākhyānikī, the engine as the conventional upajāti.
KNOWN_DIVERGENCES = {"kumarasambhava-1.1": "AKyAnikI"}

#: Verses vidyut names nothing for although the engine is right: its templates
#: are strict about the pāda-final syllable (bg-8.28 pāda a ends short where
#: indravajrā wants guru) and its pañcacāmara row is a wrong 12-syllable pattern.
VIDYUT_MISSES = {"bg-8.28", "shiva-tandava-1"}

#: Rule-defined families vidyut's table cannot name (no fixed template), so it
#: either returns nothing or a fuzzy jāti guess; they are not compared.
UNCOMPARABLE = {"anuṣṭubh", "upajāti", "āryā"}


def _slp1(verse: dict) -> str:
    return to_slp1(verse["text"], Script.IAST)


@pytest.mark.parametrize("verse", GOLDEN["verses"], ids=[v["id"] for v in GOLDEN["verses"]])
def test_vidyut_agrees_or_diverges_as_documented(verse):
    theirs = chandas._vidyut_name(_slp1(verse))
    ours = chandas.identify(_slp1(verse))
    if verse["id"] in KNOWN_DIVERGENCES:
        assert theirs == KNOWN_DIVERGENCES[verse["id"]]
        assert ours.notes == f"vidyut suggests {theirs}"
    elif verse["id"] in VIDYUT_MISSES:
        assert theirs is None
        assert ours.name is not None and ours.notes is None
    elif theirs in chandas._meter_table():
        # an exact vṛtta template from vidyut must equal ours, and leaves no note
        assert ours.name == theirs and ours.notes is None
    elif verse["meter"] not in UNCOMPARABLE:
        pytest.fail(f"{verse['id']}: vidyut found no vṛtta ({theirs!r}) for {verse['meter']}")


@pytest.mark.parametrize("verse", GOLDEN["irregular"], ids=[v["id"] for v in GOLDEN["irregular"]])
def test_both_reject_the_irregular_verse(verse):
    assert chandas._vidyut_name(_slp1(verse)) is None
    assert chandas.identify(_slp1(verse)).name is None
