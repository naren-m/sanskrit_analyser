"""Normalize any-script Sanskrit input to SLP1 words for analysis.

Daṇḍas, verse numbers and stray digits are stripped; the avagraha is
deliberately preserved — ``rAmo 'sti`` records the sandhi split for free
(design doc §3.1).
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from sanskrit_analyzer.models.scripts import Script
from sanskrit_analyzer.utils.normalize import detect_script
from sanskrit_analyzer.utils.transliterate import to_slp1

# Daṇḍa / double daṇḍa / pipe renderings, Devanagari + ASCII digits, verse-ref dots.
_STRIP = re.compile(r"[।॥|]+|[०-९0-9]+[.०-९0-9]*")
_WS = re.compile(r"\s+")
_IAST_DIACRITICS = re.compile(r"[āīūṛṝḷḹēōṃḥñṅṇṭḍśṣ]", re.IGNORECASE)
_ASCII_UPPER = re.compile(r"[A-Z]")


@dataclass(frozen=True)
class NormalizedInput:
    raw: str
    script: str
    slp1: str
    words: list[str]


def normalize(text: str) -> NormalizedInput:
    raw = text or ""
    # Strip daṇḍas/digits BEFORE detection: a Devanagari daṇḍa or verse number
    # after an IAST line would otherwise mislead detect_script.
    stripped = _WS.sub(" ", _STRIP.sub(" ", raw)).strip()
    if not stripped:
        return NormalizedInput(raw=raw, script="unknown", slp1="", words=[])
    script = detect_script(stripped)
    # detect_script routes a lone LEADING capital to IAST so English-style
    # proper nouns ("Rama") survive. Here the input is Sanskrit headed for
    # grammatical analysis: a capital with zero IAST diacritics is far more
    # likely an SLP1 word-initial aspirate (Bavati, GacCati) — prefer SLP1.
    if (
        script == Script.IAST
        and _ASCII_UPPER.search(stripped)
        and not _IAST_DIACRITICS.search(stripped)
    ):
        script = Script.SLP1
    slp1 = to_slp1(stripped, script) if script != Script.SLP1 else stripped
    # SLP1 renders daṇḍa as '.'; drop bare punctuation tokens, keep avagraha.
    words = [w.strip(".") for w in slp1.split() if w.strip(".'-")]
    return NormalizedInput(raw=raw, script=script.value, slp1=slp1, words=words)
