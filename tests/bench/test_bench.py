"""Offline unit tests for the bench helpers (no corpus, no model weights)."""
from __future__ import annotations

import json
import logging
from pathlib import Path

import pytest

from tests.bench.corpus import (
    Row,
    clean_verse,
    gold_padas,
    load_rows,
    parse_meaning,
    split_rows,
)
from tests.bench.score import lemma_match, meter_match, norm_slp1, recovered


@pytest.mark.parametrize(
    ("raw", "want"),
    [
        # trailing verse marker and glued daṇḍa
        ("तपस्वी वाग्विदां वरम् ।नारदं ।।1.1.1।।", "तपस्वी वाग्विदां वरम् नारदं"),
        # ASCII-colon visarga is a real visarga, not noise
        ("सत्यवाक्यो दृढव्रत:।।1.1.2।।", "सत्यवाक्यो दृढव्रतः"),
        # bracketed editorial note and tabs
        ("[Rama goes]\tरामो\tगच्छति ॥", "रामो गच्छति"),
        # avagraha survives
        ("सङ्गोऽस्त्वकर्मणि", "सङ्गोऽस्त्वकर्मणि"),
    ],
)
def test_clean_verse(raw: str, want: str) -> None:
    assert clean_verse(raw) == want


@pytest.mark.parametrize(
    ("line", "want"),
    [
        (
            "महाप्राज्ञः highly learned, वरम् choicest",
            {"महाप्राज्ञः": "highly learned", "वरम्": "choicest"},
        ),
        # ASCII-colon visarga in the key
        ("जनक: Janaka, उवाच spoke.", {"जनकः": "Janaka", "उवाच": "spoke"}),
        ("", {}),
    ],
)
def test_parse_meaning(line: str, want: dict[str, str]) -> None:
    assert parse_meaning(line) == want


@pytest.mark.parametrize(
    ("word", "want"),
    [
        ("rAmo", "rAmaH"),      # -o of -aH
        ("rAmas", "rAmaH"),     # pre-visarga s
        ("punar", "punaH"),     # r surface of visarga
        ("varaM", "varam"),     # anusvāra vs m
        ("vAg", "vAk"),         # final voicing
        ("rAma'", "rAma"),      # punctuation dropped
        ("niSitES", "niSitEH"),  # visarga as S before a palatal
        ("rAmaz", "rAmaH"),     # visarga as z before a retroflex
        ("puMgava", "puNkava"),  # M before a k-class stop (voicing folds g->k)
        ("saMcara", "saYcara"),  # c-class
        ("kaMwaka", "kaRwaka"),  # ṭ-class
        ("saMta", "santa"),      # t-class
        ("saMpUrRa", "sampUrRa"),  # p-class
        ("puMsa", "pumsa"),  # M before a non-stop stays m
        ("puNgava", "puNkava"),
    ],
)
def test_norm_slp1(word: str, want: str) -> None:
    assert norm_slp1(word) == want


@pytest.mark.parametrize(
    ("gold", "tokens", "want"),
    [
        (["rAmaH", "gacCati"], ["rAmo", "gacCati"], 2),
        # finer split of a compound is not penalised
        (["svADyAyaniratam"], ["svADyAya", "niratam"], 1),
        # compound members re-joined with vowel sandhi (a + A -> A, a + i -> e)
        (["kumBakarRAtmajaH"], ["kumBakarRa", "AtmajaS"], 1),
        (["gajendraH"], ["gaja", "indraH"], 1),
        # merging across a pada boundary is
        (["guRavAn", "kaH"], ["guRavAnkaH"], 0),
        (["akarmaRi"], [], 0),
        # nasal: anusvāra before its own class
        (["puMgavam"], ["puNgavam"], 1),
        (["puMgavam"], ["punGavam"], 0),    # nasal of the wrong class
        # pausal visarga: only the final one may differ
        (["saH"], ["sa"], 1),
        (["SrutaH"], ["Sruta"], 1),
        (["sa"], ["sA"], 0),
        (["rAma"], ["rAmA"], 0),
        (["saH"], ["sA"], 0),
        # gold pada glued to an enclitic
        (["putrASca"], ["putrAH", "ca"], 1),
        (["fzestu"], ["fzeH", "tu"], 1),
        (["diDakzoriva"], ["diDakzoH", "iva"], 1),
        (["putrASca"], ["putrAH", "tu"], 0),    # wrong enclitic
        (["putrASca"], ["putrAH"], 0),          # enclitic missing
        (["putrASca"], ["putrAH", "x", "ca"], 0),  # not adjacent
    ],
)
def test_recovered(gold: list[str], tokens: list[str], want: int) -> None:
    assert recovered(gold, tokens) == want


@pytest.mark.parametrize(
    ("gold", "toks", "accepted", "want"),
    [
        ("munipuNgavam", [("muni", "muni"), ("puNgavam", "puNgava")], {"munipuMgava", "puMgava"}, True),
        ("ikzvAkuvaMSapraBavaH",
         [("ikzvAku", "ikzvAku"), ("vaMSa", "vaMSa"), ("praBavaH", "praBava")],
         {"ikzvAkuvaMSapraBava", "praBava"}, True),
        ("mAtulakulam", [("mAtula", "mAtula"), ("kulam", "kula")], {"kula", "mAtulakula"}, True),
        ("niyatAtmA", [("niyata", "niyata"), ("AtmA", "Atman")], {"niyatAtman"}, True),
        ("SrutaH", [("Sruta", "Sruta")], {"Sru", "Sruta"}, True),
        ("saH", [("sa", "tad")], {"tad"}, True),
        ("putrASca", [("putrAH", "putra"), ("ca", "ca")], {"putra"}, True),
        ("fzestu", [("fzeH", "fzi"), ("tu", "tu")], {"fzi"}, True),
        ("gacCati", [("gacCati", "gamx~")], {"gam"}, True),   # anubandha strip kept
        ("munipuNgavam", [("muni", "muni"), ("puNgavam", "puNgava")], {"kula"}, False),  # wrong lemma
        ("mAtulakulam", [("mAtula", "mAtula"), ("kulam", "kula")], {"mAtulA"}, False),
        ("guRavAnkaH", [("guRavAn", "guRavat"), ("kaH", "kim")], {"guRavat"}, False),  # merge
        ("rAma", [("rAmA", "rAmA")], {"rAma"}, False),
        ("sa", [("sA", "sA")], {"tad"}, False),
    ],
)
def test_lemma_match(gold, toks, accepted, want) -> None:
    assert lemma_match(gold, toks, accepted) is want


@pytest.mark.parametrize(
    ("got", "gold", "want"),
    [
        ("anuzwuB (paTyA)", "anuzwuB (paTyA)", True),
        ("anuzwuB (paTyA)", "anuzwuB", True),       # bare family name in gold
        ("anuzwuB (na-vipulA)", "anuzwuB (paTyA)", False),
        ("anuzwuBa", "anuzwuB", False),             # prefix is not a family
        (None, "vaMSasTa", False),
    ],
)
def test_meter_match(got: str | None, gold: str, want: bool) -> None:
    assert meter_match(got, gold) is want


def test_gold_padas_split_multiword_keys() -> None:
    assert gold_padas("सःप्लवङ्गमः that monkey, तम् रामम् Rama") == ["saHplavaNgamaH", "tam", "rAmam"]


def _corpus(root: Path) -> Path:
    base = root / "data" / "slokas" / "Slokas"
    for kanda, name in ((1, "BalaKanda"), (7, "UttaraKanda")):
        d = base / name
        d.mkdir(parents=True)
        for v in (1, 2):
            ref = f"{kanda}::1::{v}::"
            (d / f"{name}_sarga_1_sloka.txt").open("a").write(
                f"{ref}रामो गच्छति ।।{kanda}.1.{v}।।\n"
            )
            (d / f"{name}_sarga_1_meaning.txt").open("a").write(f"{ref}रामः Rama, गच्छति goes\n")
            (d / f"{name}_sarga_1_translation.txt").open("a").write(f"{ref}Rama goes.\n")
    return root


def test_load_rows_and_split_by_kanda(tmp_path: Path) -> None:
    rows = load_rows(_corpus(tmp_path))
    assert len(rows) == 4
    assert rows[0] == Row("1.1.1", 1, "रामो गच्छति", "रामः Rama, गच्छति goes", "Rama goes.")
    dev, held = split_rows(rows, "dev", 10), split_rows(rows, "heldout", 10)
    assert {r.kanda for r in dev} == {1}
    assert {r.kanda for r in held} == {7}
    assert split_rows(rows, "dev", 10, seed=1) == split_rows(rows, "dev", 10, seed=1)


# --- extra corpora: Gītā (gita/gita word meanings) and label-free texts -------

from tests.bench.corpus import gita_gold, gita_roman_to_slp1, load_gita, load_plain  # noqa: E402


@pytest.mark.parametrize(
    ("roman", "want"),
    [
        ("uvācha", "uvAca"),            # ch = c
        ("ichchhā", "icCA"),            # chh = ch
        ("kṣhetre", "kzetre"),          # ṣh = ṣ
        ("śhītoṣhṇa", "SItozRa"),       # śh = ś
        ("dhṛitarāśhtraḥ", "DftarAStraH"),  # ṛi = ṛ (source lacks the ṭ dot; kept as is)
        ("saṁgaḥ", "saMgaH"),           # ṁ = ṃ
    ],
)
def test_gita_roman_to_slp1(roman: str, want: str) -> None:
    assert gita_roman_to_slp1(roman) == want


def test_gita_gold_takes_keys_and_splits_members() -> None:
    wm = "dhṛitarāśhtraḥ uvācha—Dhritarashtra said; dharma-kṣhetre—the land of dharma; cha—and"
    assert gita_gold(wm) == ["DftarAStraH", "uvAca", "Darma", "kzetre", "ca"]


def test_load_gita_and_plain(tmp_path: Path) -> None:
    src = tmp_path / "corpus_packs" / "gita" / "sources"
    src.mkdir(parents=True)
    (src / "verse.json").write_text(json.dumps([{
        "chapter_number": 2, "verse_number": 47,
        "text": "कर्मण्येवाधिकारस्ते मा फलेषु कदाचन।\n\nमा कर्मफलहेतुर्भूर्मा ते सङ्गोऽस्त्वकर्मणि।।2.47।।\n",
        "word_meanings": "karmaṇi—in action; eva—only"}]), encoding="utf-8")
    rows = load_gita(tmp_path)
    assert rows[0].ref == "BG 2.47" and rows[0].gold == ("karmaRi", "eva")
    assert rows[0].text.endswith("सङ्गोऽस्त्वकर्मणि") and "2" not in rows[0].text

    plain = tmp_path / "v.json"
    plain.write_text(json.dumps([{"chapter_num": 1, "prakarana_num": 1, "verse_num": 1,
                                  "devanagari": "वन्दे नादतनुं शङ्करम् ।"}]), encoding="utf-8")
    prow = load_plain(plain)[0]
    assert prow.ref == "1.1.1" and prow.gold == () and prow.text == "वन्दे नादतनुं शङ्करम्"


def test_agreement_is_token_f1() -> None:
    from tests.bench.run import agreement

    assert agreement([["rAmo", "gacCati"]], [["rAmaH", "gacCati"]]) == 1.0   # spelling folded
    assert agreement([["a", "b"]], [["a", "c"]]) == pytest.approx(0.5)
    assert agreement([["a"]], [[]]) == 0.0


def test_smoke_bench_runs_offline(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    import time

    from tests.bench.run import main

    out_json = tmp_path / "smoke.json"
    t0 = time.time()
    try:
        assert main(["--smoke", "--n", "1", "--out", str(out_json)]) == 0
    finally:
        # main() calls logging.disable(WARNING) for the CLI; undo it so later
        # tests in this process keep their warning logs.
        logging.disable(logging.NOTSET)
    out = capsys.readouterr().out
    assert time.time() - t0 < 60
    assert "n=1" in out and "reader-slm" not in out
    report = json.loads(out_json.read_text())
    e = report["engines"]["reader"]
    assert list(report["engines"]) == ["reader"]
    assert e["verses"] == 1 and e["coverage"] > 0.5 and e["verify"] > 0.5 and e["lemma_n"] > 0
    # The non-slow tier refuses weight loads (conftest guard), so the reader runs on
    # its DP proposer here. The ByT5 reader is measured outside the sandbox.
    assert set(e["proposers"]) == {"dp"}
