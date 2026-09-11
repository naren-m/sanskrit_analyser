"""Verse correctness engine: run gold verses through the top-level interfaces.

Loads :data:`CASES_FILE` (real Rāmāyaṇa ślokas and Yoga Sūtras with the lemmas
their corpus glosses imply), runs each verse through every public entry point
of the library, and scores each interface on how many glossed words it
recovered. Used by ``tests/corpus/test_verses.py`` and runnable directly::

    uv run python -m tests.corpus.engine

Interfaces exercised:

- ``analyzer``  — :meth:`sanskrit_analyzer.Analyzer.analyze` (vidyut + validator)
- ``deep_read`` — :meth:`sanskrit_analyzer.DeepRead.analyze` (rule segmenter + kosha; ByT5 off)
- ``prakriya``  — :func:`sanskrit_analyzer.prakriya.analyze_verse` (chandas + verified padas)

A glossed word counts as recovered when any acceptable lemma for it appears
among the lemmas *or* dhātu roots the interface produced anywhere in the verse.
"""
from __future__ import annotations

import asyncio
import json
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from sanskrit_analyzer import AnalysisMode, Analyzer, Config, DeepRead
from sanskrit_analyzer.prakriya import analyze_verse
from sanskrit_analyzer.utils.normalize import detect_script, normalize_slp1

CASES_FILE = Path(__file__).resolve().parents[1] / "data" / "corpus_verses.json"
INTERFACES = ("analyzer", "deep_read", "prakriya")

# Every Sanskrit word carries a vowel; a token without one is sandhi residue or
# punctuation that leaked through as a "word".
_SLP1_VOWEL = re.compile(r"[aAiIuUfFxXeEoO]")


@dataclass(frozen=True)
class VerseCase:
    id: str
    source: str
    ref: str
    text: str
    meter: str | None
    gloss: dict[str, list[str]]  # SLP1 word -> acceptable lemmas (SLP1)


@dataclass
class InterfaceReport:
    name: str
    tokens: list[str] = field(default_factory=list)
    lemmas: set[str] = field(default_factory=set)
    hits: dict[str, bool] = field(default_factory=dict)
    seconds: float = 0.0

    @property
    def recall(self) -> float:
        return sum(self.hits.values()) / len(self.hits) if self.hits else 0.0

    @property
    def junk(self) -> list[str]:
        return [t for t in self.tokens if not _SLP1_VOWEL.search(_slp1(t))]


@dataclass
class VerseReport:
    case: VerseCase
    interfaces: dict[str, InterfaceReport]
    chandas: str | None
    prakriya_analyses: list[tuple[str, dict[str, Any]]]


def load_cases(path: Path = CASES_FILE) -> list[VerseCase]:
    return [VerseCase(**raw) for raw in json.loads(path.read_text())]


def _slp1(text: str) -> str:
    return normalize_slp1(text, detect_script(text)) if text else ""


def _score(
    case: VerseCase, name: str, tokens: list[str], lemmas: set[str], started: float
) -> InterfaceReport:
    hits = {w: any(alt in lemmas for alt in alts) for w, alts in case.gloss.items()}
    return InterfaceReport(name, tokens, lemmas, hits, time.perf_counter() - started)


async def _run_analyzer(case: VerseCase, analyzer: Analyzer) -> InterfaceReport:
    t = time.perf_counter()
    tree = await analyzer.analyze(case.text, mode=AnalysisMode.EDUCATIONAL, bypass_cache=True)
    words = tree.all_words
    lemmas = {w.lemma for w in words} | {w.dhatu.dhatu for w in words if w.dhatu}
    return _score(case, "analyzer", [w.surface_form for w in words], lemmas, t)


def _run_deep_read(case: VerseCase, deep_read: DeepRead) -> InterfaceReport:
    t = time.perf_counter()
    tokens = deep_read.analyze(case.text, use_byt5=False).to_dict()["tokens"]
    lemmas: set[str] = set()
    for tok in tokens:
        for a in tok["analyses"]:
            lemmas.add(a.get("lemma"))
            if a.get("dhatu"):
                lemmas.add(a["dhatu"].get("root"))
    lemmas.discard(None)
    return _score(case, "deep_read", [tok["surface"] for tok in tokens], lemmas, t)


def _run_prakriya(
    case: VerseCase,
) -> tuple[InterfaceReport, str | None, list[tuple[str, dict[str, Any]]]]:
    t = time.perf_counter()
    rec = analyze_verse(case.text)
    analyses = [(p["surface"], a) for p in rec["padas"] for a in p["analyses"]]
    lemmas = {a["lemma"] for _, a in analyses}
    report = _score(case, "prakriya", [p["surface"] for p in rec["padas"]], lemmas, t)
    chandas = rec["chandas"]["name"] if rec["chandas"] else None
    return report, chandas, analyses


async def run_case(case: VerseCase, analyzer: Analyzer, deep_read: DeepRead) -> VerseReport:
    prakriya, chandas, analyses = _run_prakriya(case)
    interfaces = {
        "analyzer": await _run_analyzer(case, analyzer),
        "deep_read": _run_deep_read(case, deep_read),
        "prakriya": prakriya,
    }
    return VerseReport(case, interfaces, chandas, analyses)


def _offline_analyzer() -> Analyzer:
    config = Config()
    config.cache.redis_enabled = False
    config.cache.sqlite_enabled = False
    return Analyzer(config)


def run_cases(cases: list[VerseCase]) -> list[VerseReport]:
    """Run every case through all interfaces (fresh engines, no persistent cache)."""

    async def _all() -> list[VerseReport]:
        analyzer, deep_read = _offline_analyzer(), DeepRead()
        return [await run_case(c, analyzer, deep_read) for c in cases]

    return asyncio.run(_all())


def format_report(reports: list[VerseReport]) -> str:
    head = f"{'verse':<20}{'meter':<22}" + "".join(f"{i:>12}" for i in INTERFACES)
    lines = [head, "-" * len(head)]
    for r in reports:
        cells = "".join(f"{r.interfaces[i].recall:>11.0%} " for i in INTERFACES)
        lines.append(f"{r.case.id:<20}{(r.chandas or '-'):<22}{cells}")
    lines.append("-" * len(head))
    for i in INTERFACES:
        hits = sum(sum(r.interfaces[i].hits.values()) for r in reports)
        total = sum(len(r.interfaces[i].hits) for r in reports)
        junk = sum(len(r.interfaces[i].junk) for r in reports)
        secs = sum(r.interfaces[i].seconds for r in reports)
        lines.append(
            f"{i:<12} recall {hits}/{total} ({hits / total:.0%})  junk tokens {junk}  {secs:.1f}s"
        )
    for r in reports:
        for i in INTERFACES:
            ir = r.interfaces[i]
            missed = [w for w, hit in ir.hits.items() if not hit]
            if missed or ir.junk:
                lines.append(f"  {r.case.id:<18}{i:<10} missed {missed}  junk {ir.junk}")
    return "\n".join(lines)


if __name__ == "__main__":
    print(format_report(run_cases(load_cases())))
