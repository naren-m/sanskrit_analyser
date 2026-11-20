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
    # Gold padas (SLP1) when they do not come from an IITK gloss line.
    # () = this corpus has no gold; None = parse `meaning` with gold_padas().
    gold: tuple[str, ...] | None = None


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


# --- other corpora: text the DCS-trained proposer never saw ------------------

_GITA_ROMAN = (("chh", "\x00"), ("ch", "c"), ("\x00", "ch"), ("śh", "ś"), ("ṣh", "ṣ"),
               ("ṛi", "ṛ"), ("ṝi", "ṝ"), ("ṁ", "ṃ"), ("’", "'"))


def gita_roman_to_slp1(word: str) -> str:
    """gita/gita's romanization (uvācha, kṣhetre, ṛi) -> SLP1."""
    for old, new in _GITA_ROMAN:
        word = word.replace(old, new)
    return transliterate(word, Script.IAST, Script.SLP1)


def gita_gold(word_meanings: str) -> list[str]:
    """Gold pieces from "key—meaning; key—meaning": keys split on spaces and hyphens."""
    out: list[str] = []
    for item in (word_meanings or "").split(";"):
        key = item.split("—", 1)[0] if "—" in item else ""
        out += [gita_roman_to_slp1(piece) for piece in re.split(r"[\s-]+", key.strip()) if piece]
    return out


def load_gita(ramayanam_root: Path) -> list[Row]:
    """Bhagavadgītā from ramayanam's gita pack (github.com/gita/gita verse.json).

    Gold is the human word-by-word key list. It is independent of DCS, splits
    compounds to members, and has some spelling noise (dhṛitarāśhtra without
    the ṭ dot), so read scores as relative between engines, not absolute.
    """
    import json

    path = Path(ramayanam_root) / "corpus_packs" / "gita" / "sources" / "verse.json"
    rows = []
    for v in json.loads(path.read_text(encoding="utf-8")):
        gold = tuple(gita_gold(v.get("word_meanings", "")))
        if gold:
            rows.append(Row(f"BG {v['chapter_number']}.{v['verse_number']}", 0,
                            clean_verse(v["text"]), "", "", gold))
    return rows


def load_plain(path: Path) -> list[Row]:
    """A corpus with no gold (JSON list with a "devanagari" field), e.g. the
    Saṅgītaratnākara. Only label-free metrics apply: verify, coverage, agreement."""
    import json

    rows = []
    for v in json.loads(Path(path).read_text(encoding="utf-8")):
        text = clean_verse(v.get("devanagari", ""))
        if text:
            ref = ".".join(str(v.get(k, "")) for k in ("chapter_num", "prakarana_num", "verse_num"))
            rows.append(Row(ref, 0, text, "", "", ()))
    return rows


def sample(rows: list[Row], n: int, seed: int = 0) -> list[Row]:
    rows = list(rows)
    random.Random(seed).shuffle(rows)
    return rows[:n]
