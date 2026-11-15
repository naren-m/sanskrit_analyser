"""Offline unit tests for the bench helpers (no corpus, no model weights)."""
from __future__ import annotations

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
from tests.bench.score import meter_match, norm_slp1, recovered


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
        ("महाप्राज्ञः highly learned, वरम् choicest", {"महाप्राज्ञः": "highly learned", "वरम्": "choicest"}),
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
    ],
)
def test_recovered(gold: list[str], tokens: list[str], want: int) -> None:
    assert recovered(gold, tokens) == want


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
            (d / f"{name}_sarga_1_sloka.txt").open("a").write(f"{ref}रामो गच्छति ।।{kanda}.1.{v}।।\n")
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
