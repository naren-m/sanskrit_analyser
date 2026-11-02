"""Sūtra code -> (text, Kāśikā gloss, English) lookup for prakriyā traces.

Sūtra texts come from ``vidyut.prakriya.Data.load_sutras()`` (Aṣṭādhyāyī,
vārttikas, Dhātupāṭha etc. — 5k+ rows keyed by code). The Kāśikā and Vasu's
English summary come from the ashtadhyayi.com data (all 3983 sūtras, see
:mod:`sanskrit_analyzer.ashtadhyayi_data`) when it is installed; otherwise the
Kāśikā falls back to the vidyut bundle's 9-row ``kashika.tsv`` stub and
English is absent. Both stay Optional: vārttikas and Dhātupāṭha codes have
neither.
"""
from __future__ import annotations

import csv
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from sanskrit_analyzer import ashtadhyayi_data
from sanskrit_analyzer.vidyut_data import VidyutUnavailable, resolve_data_dir


@dataclass(frozen=True)
class Sutra:
    code: str          # e.g. "3.4.78"
    source: str        # e.g. "ashtadhyayi", "dhatupatha"
    text: str          # sūtra text in SLP1
    kashika: str | None = None  # Kāśikā vṛtti in SLP1
    english: str | None = None  # Vasu's English summary


class SutraIndex:
    def __init__(self, sutras: dict[str, Sutra]):
        self._sutras = sutras

    @classmethod
    def load(
        cls, data_dir: Path | None = None, ashtadhyayi_dir: Path | None = None
    ) -> SutraIndex:
        data_dir = data_dir or resolve_data_dir()
        if data_dir is None:
            raise VidyutUnavailable(
                "vidyut data bundle not found; cannot build sūtra index."
            )
        from vidyut.prakriya import Data

        kashika = _load_kashika(data_dir / "prakriya" / "kashika.tsv")
        kashika.update(_slp1_values(
            ashtadhyayi_data.load_commentary("kashika", ashtadhyayi_dir)
        ))
        english = ashtadhyayi_data.load_commentary(
            "vasu_english_summary", ashtadhyayi_dir
        )
        sutras: dict[str, Sutra] = {}
        for s in Data(str(data_dir / "prakriya")).load_sutras():
            # Later sources may repeat a code; first (Aṣṭādhyāyī) wins.
            sutras.setdefault(
                s.code,
                Sutra(
                    code=s.code,
                    source=str(s.source),
                    text=s.text,
                    kashika=kashika.get(s.code),
                    english=english.get(s.code),
                ),
            )
        return cls(sutras)

    def lookup(self, code: str) -> Sutra | None:
        return self._sutras.get(code)

    def __len__(self) -> int:
        return len(self._sutras)


def _load_kashika(path: Path) -> dict[str, str]:
    """Parse kashika.tsv (columns: code, text). Missing/short file is fine."""
    if not path.is_file():
        return {}
    out: dict[str, str] = {}
    with path.open(encoding="utf-8") as fh:
        for row in csv.DictReader(fh, delimiter="\t"):
            code, text = row.get("code"), row.get("text")
            if code and text:
                out[code] = text
    return out


def _slp1_values(devanagari: dict[str, str]) -> dict[str, str]:
    """Transliterate glosses to SLP1 so they match ``Sutra.text``."""
    if not devanagari:
        return {}
    from vidyut.lipi import Scheme, transliterate

    return {
        code: transliterate(text, Scheme.Devanagari, Scheme.Slp1)
        for code, text in devanagari.items()
    }


@lru_cache(maxsize=1)
def get_index() -> SutraIndex:
    return SutraIndex.load()
