"""Verse-level facade: normalize -> chandas -> per-word verified analyses."""
from __future__ import annotations

import logging

from sanskrit_analyzer.prakriya import chandas as chandas_mod
from sanskrit_analyzer.prakriya.analyzer import analyze_pada
from sanskrit_analyzer.prakriya.normalize import normalize

logger = logging.getLogger(__name__)


def analyze_verse(text: str, limit_per_word: int = 5) -> dict:
    n = normalize(text)
    record: dict = {
        "input": {"raw": n.raw, "script": n.script, "slp1": n.slp1},
        "chandas": None,
        "padas": [],
    }
    if n.words and chandas_mod.is_available():
        try:
            c = chandas_mod.identify(n.slp1)
            record["chandas"] = {"name": c.name, "scans": c.scans, "notes": c.notes}
        except Exception as exc:
            logger.warning("chandas identification failed: %s", exc)
    for word in n.words:
        record["padas"].append(
            {
                "surface": word,
                "analyses": [
                    a.to_dict() for a in analyze_pada(word, limit=limit_per_word)
                ],
            }
        )
    return record
