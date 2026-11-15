"""Rāmāyaṇa rows for the bench, read at run time from a ramayanam checkout.

Nothing from the corpus is committed to this repo. The licence of the IITK
word-by-word glosses and translations is not settled, so the bench reads
``data/slokas/Slokas`` from the path given on the command line.

Split rule (by work, never by line): kāṇḍas 1-6 are ``dev``, kāṇḍa 7
(Uttara) is ``heldout``. Held-out rows are for measurement only. Never tune
a weight, prompt or threshold against them.
"""
from __future__ import annotations

import random
import re
from dataclasses import dataclass
from pathlib import Path

from sanskrit_analyzer.models.scripts import Script
from sanskrit_analyzer.utils import transliterate

KANDAS = {
    1: "BalaKanda", 2: "AyodhyaKanda", 3: "AranyaKanda", 4: "KishkindaKanda",
    5: "SundaraKanda", 6: "YuddhaKanda", 7: "UttaraKanda",
}
SPLITS = {"dev": frozenset(range(1, 7)), "heldout": frozenset({7})}

# The corpus writes visarga as an ASCII colon after a Devanagari letter.
_COLON_VISARGA = re.compile(r"(?<=[ऀ-ॿ]):")
_DEVANAGARI = re.compile(r"[ऀ-ॿ]")
# A gloss line is "देव-word english, देव-word english, ...".
_PAIR = re.compile(r"([ऀ-ॿ][ऀ-ॿ:\s]*?)\s+([^,ऀ-ॿ][^,]*)")


@dataclass(frozen=True)
class Row:
    ref: str            # "kanda.sarga.sloka"
    kanda: int
    text: str           # cleaned Devanagari verse
    meaning: str        # raw word-by-word gloss line
    translation: str


def clean_verse(raw: str) -> str:
    """Corpus line -> Devanagari padas separated by single spaces.

    Drops ``[editorial notes]`` and ``।।1.1.1।।`` markers, keeps avagraha,
    turns the ASCII-colon visarga into ``ः``, and replaces daṇḍas with spaces
    (a daṇḍa glued to the next word is otherwise segmented as part of it).
    """
    text = re.sub(r"\[[^\]]*\]", " ", raw or "")
    text = _COLON_VISARGA.sub("ः", text)
    text = re.sub(r"[।॥]", " ", text)
    text = "".join(ch for ch in text if _DEVANAGARI.match(ch) or ch.isspace())
    # Daṇḍas are gone; any digits left were Devanagari verse numbers.
    text = re.sub(r"[०-९]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def parse_meaning(line: str) -> dict[str, str]:
    """Gloss line -> {Devanagari key: English gloss}."""
    pairs: dict[str, str] = {}
    for dev, gloss in _PAIR.findall(line or ""):
        dev = dev.strip().replace(":", "ः")
        gloss = gloss.strip().rstrip(".").strip()
        if dev and gloss:
            pairs[dev] = gloss
    return pairs


def gold_padas(meaning: str) -> list[str]:
    """SLP1 gold padas of a gloss line. Multi-word keys are split on spaces."""
    return [
        transliterate(word, Script.DEVANAGARI, Script.SLP1)
        for key in parse_meaning(meaning)
        for word in key.split()
    ]


def _read(path: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    if not path.exists():
        return out
    for line in path.read_text(encoding="utf-8").splitlines():
        parts = line.split("::", 3)
        if len(parts) == 4:
            out[".".join(parts[:3])] = parts[3].strip()
    return out


def load_rows(ramayanam_root: Path) -> list[Row]:
    """Every śloka that has a gloss line, in corpus order."""
    base = Path(ramayanam_root) / "data" / "slokas" / "Slokas"
    rows: list[Row] = []
    for kanda, name in KANDAS.items():
        for sloka_file in sorted(
            (base / name).glob(f"{name}_sarga_*_sloka.txt"),
            key=lambda p: int(p.stem.split("_")[2]),
        ):
            stem = str(sloka_file)[: -len("_sloka.txt")]
            slokas = _read(sloka_file)
            meanings = _read(Path(stem + "_meaning.txt"))
            translations = _read(Path(stem + "_translation.txt"))
            for ref, raw in slokas.items():
                if meanings.get(ref):
                    rows.append(Row(ref, kanda, clean_verse(raw), meanings[ref],
                                    translations.get(ref, "")))
    return rows


def split_rows(rows: list[Row], split: str, n: int, seed: int = 0) -> list[Row]:
    """Deterministic sample of ``n`` rows from one split."""
    pool = [r for r in rows if r.kanda in SPLITS[split]]
    random.Random(seed).shuffle(pool)
    return pool[:n]
