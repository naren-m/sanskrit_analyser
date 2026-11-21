"""Pāṇini re-join validator (issue #75, phase A): rule-table joins and split licensing."""
from __future__ import annotations

import csv
from pathlib import Path

import pytest

from sanskrit_analyzer.prakriya import sutra_index
from sanskrit_analyzer.reader import read as read_mod
from sanskrit_analyzer.reader.sandhi import rejoin, split_is_licensed
from sanskrit_analyzer.vidyut_data import resolve_data_dir

BG_2_47 = ("karmaRyevADikAras te mA Palezu kadAcana | mA karmaPalaheturBUr mA te "
           "saNgo 'stv akarmaRi")
BG_2_47_PADAS = ("karmaRi eva aDikAraH te mA Palezu kadAcana | mA karmaPalahetuH BUH mA te "
                 "saNgaH astu akarmaRi").split()
BG_2_20 = ("na jAyate mriyate vA kadAcin nAyaM BUtvA BavitA vA na BUyaH | ajo nityaH "
           "SASvato 'yaM purARo na hanyate hanyamAne SarIre")
BG_2_20_PADAS = ("na jAyate mriyate vA kadAcit na ayaM BUtvA BavitA vA na BUyaH | ajaH nityaH "
                 "SASvataH ayaM purARaH na hanyate hanyamAne SarIre").split()
# Doubled-word fixture in the shape of Rām. 2.105.41 (the verse text is not in the repo).
RAMA_TEXT = "tvaM hi rAjA tvaM pitA"
RAMA_PADAS = ["tvam", "tvam", "hi", "rAjA", "tvam", "pitA"]

#: (text, padas, licensed, a sūtra code cited by the matching join)
CASES = {
    "rAmaH gacCati": ("rAmo gacCati", ["rAmaH", "gacCati"], True, "6.1.113–114"),
    "tat SrutvA": ("tacCrutvA", ["tat", "SrutvA"], True, "8.4.40"),
    "tad hitam": ("tadDitam", ["tad", "hitam"], True, "8.4.62"),
    "saNgaH astu": ("saNgo'stu", ["saNgaH", "astu"], True, "6.1.113"),
    "punar api": ("punarapi", ["punar", "api"], True, "8.3.15"),
    "rAmas calati": ("rAmaScalati", ["rAmas", "calati"], True, "8.3.34"),
    "BG 2.47 full": (BG_2_47, BG_2_47_PADAS, True, "6.1.113"),
    "BG 2.20 hanyate dropped": (BG_2_20, [p for p in BG_2_20_PADAS if p != "hanyate"], False, None),
    "Ram doubled tvam": (RAMA_TEXT, RAMA_PADAS, False, None),
}


@pytest.mark.parametrize("text,padas,ok,sutra", CASES.values(), ids=CASES.keys())
def test_split_is_licensed(text, padas, ok, sutra):
    lic = split_is_licensed(text, padas)
    assert lic.ok is ok
    if ok:
        cited = {j.sutra.split()[0] for j in lic.rejoin.junctions if j.sutra}
        assert sutra in cited
    else:
        assert lic.rejoin is None


def test_rejoin_lists_every_rule_and_marks_verbatim():
    assert [r.surface for r in rejoin(["rAmaH", "gacCati"])] == ["rAmo gacCati"]
    verbatim = rejoin(["na", "jAyate"])[0].junctions[0]
    assert verbatim.rule is None and verbatim.sutra is None


def test_extra_rows_are_annotated_and_cite_real_sutras():
    path = Path(__file__).resolve().parents[2] / "sanskrit_analyzer/data/sandhi-rules-extra.csv"
    rows = list(csv.DictReader(path.open(encoding="utf-8")))
    assert rows
    for row in rows:
        assert row["category"] and row["sandhi_name"] and row["sutra"]
        if resolve_data_dir():
            assert sutra_index.get_index().lookup(row["sutra"].split()[0]) is not None


def test_read_sloka_carries_split_field(monkeypatch):
    def word(s):
        return {"surface": s, "verified": True, "source": "kosha", "index": 0}

    monkeypatch.setattr(read_mod, "read_words",
                        lambda text, proposer="byt5": ([word("rAmaH"), word("gacCati")], "test"))
    split = read_mod.read_sloka("rAmo gacCati")["split"]
    assert split == {"licensed": True, "unruled_junctions": 0, "sutras": ["6.1.113–114"]}
