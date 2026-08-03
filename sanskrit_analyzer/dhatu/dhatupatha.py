"""Dhātupāṭha lookup and Pāṇinian it-marker (anubandha) stripping.

The Dhātupāṭha cites roots in a conventional form carrying markers that are
not part of the root: ḍukṛñ is √kṛ, ñiṣvapa is √svap. This module strips
them heuristically and indexes the resulting clean roots.

Two CSVs back it: ``dhatus-full.csv`` (2259 roots, machine-derived) merged
with ``dhatus-core.csv`` (294 hand-curated clean roots). Where a root is
curated, that reading wins — the heuristic is only the fallback.
"""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

_DATA_DIR = Path(__file__).resolve().parent.parent / "data"

VOWELS: set[str] = set("aAiIuUfFxXeEoO")
CONSONANTS: set[str] = set("kKgGNcCjJYwWqQRtTdDnpPbBmyrlvSzsh")

#: Traditional Dhātupāṭha "cutu" it-clusters conventionally prefixed to a
#: root purely to disambiguate it in the recitation list (e.g. "qukfY" for
#: kf, "quBf\\Y" for Bf).
_IT_PREFIX_CLUSTERS = ("qu", "wu", "Qu", "Wu", "Gu")


def strip_anubandhas(upadesha: str) -> str:
    """Strip Pāṇinian it-markers from a dhātu's upadeśa (citation) form.

    Deliberately NOT a full implementation of the it-saṃjñā sūtras
    (Aṣṭādhyāyī 1.3.2-1.3.9), which require per-root knowledge of which
    letters are markers versus real phonemes — that is why dhatus-core.csv
    exists as a hand-curated table. Callers should prefer the curated
    ``core_root`` when a root is in it; this is the fallback for the rest.
    """
    s = upadesha.replace("^", "").replace("\\", "")

    for prefix in _IT_PREFIX_CLUSTERS:
        if s.startswith(prefix) and len(s) > len(prefix) + 1:
            s = s[len(prefix):]
            break

    if s.endswith("~"):
        s = s[:-1]
        if s and s[-1] in VOWELS:
            s = s[:-1]
    elif s and s[-1] in CONSONANTS:
        s = s[:-1]

    return s


class DhatuKosha:
    """Merged Dhātupāṭha index keyed by resolved clean root."""

    def __init__(
        self,
        full_path: str | Path | None = None,
        core_path: str | Path | None = None,
    ) -> None:
        full_p = Path(full_path) if full_path else _DATA_DIR / "dhatus-full.csv"
        core_p = Path(core_path) if core_path else _DATA_DIR / "dhatus-core.csv"

        with open(core_p, encoding="utf-8") as f:
            core_by_code = {r["code"]: r["core_root"] for r in csv.DictReader(f)}

        with open(full_p, encoding="utf-8") as f:
            rows = list(csv.DictReader(f))

        self.entries: list[dict[str, Any]] = []
        for r in rows:
            entry: dict[str, Any] = dict(r)
            curated_root = core_by_code.get(r["code"])
            if curated_root is not None:
                entry["core_root"] = curated_root
                entry["curated"] = True
            else:
                entry["core_root"] = strip_anubandhas(r["dhatu_slp1"])
                entry["curated"] = False
            self.entries.append(entry)

    def lookup(self, root: str) -> list[dict[str, Any]]:
        """Every entry whose resolved core_root equals ``root`` exactly."""
        return [e for e in self.entries if e["core_root"] == root]

    def by_gana(self, gana: int) -> list[dict[str, Any]]:
        """Every entry in a given gaṇa (1-10)."""
        return [e for e in self.entries if int(e["gana"]) == int(gana)]

    def all_roots(self) -> list[str]:
        """Return the sorted set of unique resolved clean roots."""
        return sorted({e["core_root"] for e in self.entries})
