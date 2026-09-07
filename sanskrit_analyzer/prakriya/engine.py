"""Verse-level facade: normalize -> chandas -> per-word verified analyses."""
from __future__ import annotations

import logging

from sanskrit_analyzer.prakriya import chandas as chandas_mod
from sanskrit_analyzer.prakriya.analyzer import analyze_pada
from sanskrit_analyzer.prakriya.normalize import normalize

logger = logging.getLogger(__name__)


def _chandas_record(c: chandas_mod.ChandasResult) -> dict:
    """Flatten a ChandasResult for the response.

    The display fields are additive: consumers reading only "name" or "scans"
    are unaffected, and they are absent when the meter carries no MeterInfo.
    """
    record: dict[str, object] = {"name": c.name, "scans": c.scans, "notes": c.notes}
    if c.info is not None:
        record.update(
            name_iast=c.info.name_iast,
            name_devanagari=c.info.name_deva,
            syllables=c.info.syllables,
            ganas=c.info.ganas,
            yati=list(c.info.yati),
        )
    return record


def analyze_verse(text: str, limit_per_word: int = 5) -> dict:
    n = normalize(text)
    record: dict = {
        "input": {"raw": n.raw, "script": n.script, "slp1": n.slp1},
        "chandas": None,
        "padas": [],
    }
    if n.words and chandas_mod.is_available():
        try:
            record["chandas"] = _chandas_record(chandas_mod.identify(n.slp1))
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
