"""The bundled derived CSVs must stay reconciled with the vidyut data bundle.

``sandhi-rules-full.csv`` and ``meters-full.csv`` are enrichments of
``sandhi/rules.csv`` and ``chandas/meters.tsv``: the leading columns are copied
verbatim from vidyut, the trailing ones (IAST, category, sandhi name, sūtra,
gaṇas, yati) are ours. Nothing stops a vidyut version bump from moving the base
data out from under them, so re-derive it here and compare.
"""

from __future__ import annotations

import csv
from pathlib import Path

import pytest

from sanskrit_analyzer.prakriya import sutra_index
from sanskrit_analyzer.vidyut_data import resolve_data_dir

DATA = Path(__file__).resolve().parents[2] / "sanskrit_analyzer" / "data"

pytestmark = pytest.mark.skipif(not resolve_data_dir(), reason="vidyut data bundle not available")

# Citations that name a span of sūtras rather than a single one, plus the
# placeholder used where no single sūtra governs the rule. Not lookup keys.
NON_ATOMIC_CITATIONS = {"6.1.113–114", "8.3.19–22", "8.3–8.4", "—"}


@pytest.fixture(scope="module")
def index() -> sutra_index.SutraIndex:
    return sutra_index.get_index()


def _rows(name: str) -> list[dict[str, str]]:
    with (DATA / name).open(encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def test_sandhi_csv_triples_match_vidyut():
    """The SLP1 (first, second, result) triples are vidyut's rules.csv verbatim."""
    with (resolve_data_dir() / "sandhi" / "rules.csv").open(encoding="utf-8") as fh:
        upstream = {(r["first"], r["second"], r["result"]) for r in csv.DictReader(fh)}
    ours = {
        (r["first_slp1"], r["second_slp1"], r["result_slp1"])
        for r in _rows("sandhi-rules-full.csv")
    }
    assert ours == upstream


def test_every_sandhi_row_is_annotated():
    """The enrichment columns are the whole point; none may be blank."""
    for row in _rows("sandhi-rules-full.csv"):
        label = f"{row['first_slp1']}+{row['second_slp1']}"
        assert row["category"], f"{label}: no category"
        assert row["sandhi_name"], f"{label}: no sandhi name"
        assert row["sutra"], f"{label}: no sūtra citation"


def _cited_sutra_codes() -> list[str]:
    """The distinct single-sūtra codes cited by ``sandhi-rules-full.csv``.

    A citation carries the sūtra text and any further references after the
    number, so only the leading token is a code to look up.
    """
    codes = {row["sutra"].split()[0] for row in _rows("sandhi-rules-full.csv")}
    return sorted(codes - NON_ATOMIC_CITATIONS)


@pytest.mark.parametrize("code", _cited_sutra_codes())
def test_sandhi_csv_cites_real_sutra(index, code):
    assert index.lookup(code) is not None, f"no sūtra {code}"


def test_meters_csv_matches_vidyut():
    """Name/class/pattern are vidyut's meters.tsv; duplicate names are kept."""
    with (resolve_data_dir() / "chandas" / "meters.tsv").open(encoding="utf-8") as fh:
        upstream = sorted(tuple(line.rstrip("\n").split("\t")) for line in fh if line.strip())
    ours = sorted((r["name_slp1"], r["class"], r["pattern"]) for r in _rows("meters-full.csv"))
    assert ours == upstream


def test_every_meter_has_gana_decomposition():
    """Every upstream meter carries our added gaṇa and display columns."""
    for row in _rows("meters-full.csv"):
        assert row["ganas"], f"{row['name_slp1']}: no gaṇa decomposition"
        assert row["name_iast"] and row["name_deva"], f"{row['name_slp1']}: no display form"
