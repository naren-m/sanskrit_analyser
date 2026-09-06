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
from functools import lru_cache
from pathlib import Path
from typing import Any

from sanskrit_analyzer.models.scripts import Script
from sanskrit_analyzer.utils.normalize import normalize_slp1
from sanskrit_analyzer.utils.transliterate import to_devanagari, to_iast

_DATA_DIR = Path(__file__).resolve().parent.parent / "data"

VOWELS: set[str] = set("aAiIuUfFxXeEoO")
CONSONANTS: set[str] = set("kKgGNcCjJYwWqQRtTdDnpPbBmyrlvSzsh")

#: Columns :meth:`DhatuKosha.search` matches against.
_ROOT_FIELDS = ("core_root", "dhatu_slp1", "dhatu_iast", "dhatu_deva")
_ARTHA_FIELDS = ("artha_slp1", "artha_iast", "artha_deva")

#: Traditional Dhātupāṭha it-clusters prefixed to a root purely to
#: disambiguate it in the recitation list: ḍukṛñ is √kṛ, ñiṣvapa is √svap.
#: "Gu" is deliberately absent — eleven roots (√ghuṇ, √ghūrṇ, √ghuṣ ...) own
#: that ghu- as their own initial, and stripping it left a bare consonant.
_IT_PREFIX_CLUSTERS = ("qu", "wu", "Yi")

#: The ovit marker, written with a tilde of its own and standing before the
#: root (ohāk = √hā). It may follow another cluster: ṭuosphūrjā.
_IT_PREFIX_OVIT = "o~"


def strip_anubandhas(upadesha: str) -> str:
    """Strip Pāṇinian it-markers from a dhātu's upadeśa (citation) form.

    Deliberately NOT a full implementation of the it-saṃjñā sūtras
    (Aṣṭādhyāyī 1.3.2-1.3.9), which require per-root knowledge of which
    letters are markers versus real phonemes — that is why dhatus-core.csv
    exists as a hand-curated table. Callers should prefer the curated
    ``core_root`` when a root is in it; this is the fallback for the rest.
    """
    s = upadesha.replace("^", "").replace("\\", "")

    # Leading markers may stack (ṭu + o~ + sphūrjā), so peel until none match.
    peeled = True
    while peeled:
        peeled = False
        for prefix in _IT_PREFIX_CLUSTERS:
            if s.startswith(prefix) and len(s) > len(prefix) + 1:
                s = s[len(prefix):]
                peeled = True
                break
        if s.startswith(_IT_PREFIX_OVIT) and len(s) > len(_IT_PREFIX_OVIT) + 1:
            s = s[len(_IT_PREFIX_OVIT):]
            peeled = True

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

    def find(self, query: str) -> list[dict[str, Any]]:
        """Look up a root written in any script (Devanagari, IAST or SLP1).

        Tries the resolved clean root, its Dhātupāṭha citation spellings, the
        full citation form (so ``ḍukṛñ`` finds √kṛ), and finally the citation
        form with its it-markers stripped.
        """
        slp = to_slp1_query(query)
        if not slp:
            return []
        for candidate in _citation_variants(slp):
            hits = self.lookup(candidate)
            if hits:
                return hits
        hits = [e for e in self.entries if e["dhatu_slp1"] == slp]
        if hits:
            return hits
        stripped = strip_anubandhas(slp)
        return self.lookup(stripped) if stripped != slp else []

    def by_gana(self, gana: int) -> list[dict[str, Any]]:
        """Every entry in a given gaṇa (1-10)."""
        return [e for e in self.entries if int(e["gana"]) == gana]

    def search(
        self, query: str, limit: int = 20, artha_only: bool = False
    ) -> list[dict[str, Any]]:
        """Entries whose root or artha (gloss) contains ``query``.

        The query may be Devanagari, IAST or SLP1. Exact root matches come
        first; ``artha_only`` matches the Sanskrit gloss alone and drops that
        exact-root head.
        """
        raw = query.strip().lower()
        if not raw:
            return []
        slp = to_slp1_query(query)
        fields = _ARTHA_FIELDS if artha_only else _ROOT_FIELDS + _ARTHA_FIELDS
        results: list[dict[str, Any]] = [] if artha_only else self.find(query)
        seen = {id(e) for e in results}
        for entry in self.entries:
            if len(results) >= limit:
                break
            if id(entry) in seen:
                continue
            haystack = " ".join(entry[f] for f in fields)
            # SLP1 is case-significant (BU is not bu), so that needle is matched
            # as-is; the raw query is matched case-insensitively.
            if (slp and slp in haystack) or raw in haystack.lower():
                results.append(entry)
                seen.add(id(entry))
        return results[:limit]

    def count(self) -> int:
        """Number of Dhātupāṭha entries."""
        return len(self.entries)

    def gana_stats(self) -> dict[int, int]:
        """Entry count per gaṇa."""
        stats: dict[int, int] = {}
        for entry in self.entries:
            gana = int(entry["gana"])
            stats[gana] = stats.get(gana, 0) + 1
        return dict(sorted(stats.items()))

    def all_roots(self) -> list[str]:
        """Return the sorted set of unique resolved clean roots."""
        return sorted({e["core_root"] for e in self.entries})


#: The Dhātupāṭha cites roots with an initial ṣ or ṇ where the living root has
#: s or n — Pāṇini 6.1.64 (dhātvādeḥ ṣaḥ saḥ) and 6.1.65 (ṇo naḥ) undo it. A
#: caller types √nah or √sthā, but the index holds ṇah and ṣṭhā.
_DENTAL_TO_RETROFLEX = {"t": "w", "T": "W", "d": "q", "D": "Q", "n": "R"}


_RETROFLEX_TO_DENTAL = {v: k for k, v in _DENTAL_TO_RETROFLEX.items()}


def undo_citation_spelling(root: str) -> str:
    """Turn a Dhātupāṭha citation spelling into the living root.

    The Dhātupāṭha writes a root-initial s as ṣ and a root-initial n as ṇ;
    Pāṇini 6.1.64 (dhātvādeḥ ṣaḥ saḥ) and 6.1.65 (ṇo naḥ) undo that when the
    root is actually used. Since ṣṭutva (8.4.41) retroflexed the rest of the
    cluster too, undoing the ṣ has to de-retroflex what follows: ṣṭhā -> sthā,
    ṣṇā -> snā. Reporting ṇah or ṣṭhā as the root shows a form that does not
    exist outside the recitation list.
    """
    if root.startswith("R"):
        return "n" + root[1:]
    if root.startswith("z") and len(root) > 1:
        rest = root[1:]
        return "s" + _RETROFLEX_TO_DENTAL.get(rest[0], rest[0]) + rest[1:]
    return root


def _citation_variants(slp: str) -> list[str]:
    """Spellings of ``slp`` to try against the Dhātupāṭha index, best first."""
    variants = [slp]
    # A nasal before a palatal is written ñ (√rañj); the index spells it n.
    if "Y" in slp:
        variants.append(slp.replace("Y", "n"))
    if slp.startswith("n"):
        variants.append("R" + slp[1:])
    elif slp.startswith("s") and len(slp) > 1:
        # ṣṭutva (8.4.41) retroflexes what follows the ṣ too: sthā -> ṣṭhā.
        rest = slp[1:]
        retroflexed = _DENTAL_TO_RETROFLEX.get(rest[0], rest[0]) + rest[1:]
        variants.append("z" + retroflexed)
        if retroflexed != rest:
            variants.append("z" + rest)
    return variants


def to_slp1_query(query: str) -> str:
    """Normalize a user-supplied root/gloss to SLP1 for matching.

    Plain ASCII is read as IAST ("gam", "bhu"), which is what an API caller
    types; SLP1 input ("BU", "kf") is detected by its own markers and passes
    through unchanged.
    """
    try:
        return normalize_slp1(query.strip())
    except Exception:
        return query.strip()


def entry_to_dict(entry: dict[str, Any]) -> dict[str, Any]:
    """Public shape of one Dhātupāṭha entry, shared by the API and MCP tools.

    ``root_*`` is the living root and ``upadesha_*`` the Dhātupāṭha's own
    citation of it, so √nah is reported as nah with upadeśa ṇah rather than as
    the non-existent √ṇah. The index key itself keeps the cited spelling; only
    the presented root is normalized.
    """
    root = undo_citation_spelling(entry["core_root"])
    return {
        "code": entry["code"],
        "root_slp1": root,
        "root_iast": to_iast(root, Script.SLP1),
        "root_devanagari": to_devanagari(root, Script.SLP1),
        "upadesha_slp1": entry["dhatu_slp1"],
        "upadesha_iast": entry["dhatu_iast"],
        "upadesha_devanagari": entry["dhatu_deva"],
        "gana": int(entry["gana"]),
        "gana_name": entry["gana_name"],
        "artha_slp1": entry["artha_slp1"],
        "artha_iast": entry["artha_iast"],
        "artha_devanagari": entry["artha_deva"],
        "curated": entry["curated"],
    }


@lru_cache(maxsize=1)
def get_dhatu_kosha() -> DhatuKosha:
    """Process-wide Dhātupāṭha index (parsing the CSVs is not free)."""
    return DhatuKosha()
