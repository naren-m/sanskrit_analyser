"""SanskritBench-local: one per-layer scoreboard for verse understanding.

Phase 0 of ``~/Projects/llms/sanskrit-understanding-plan.md``. Each row of the
report is one engine; each column is one layer of understanding. The first run
on ``main`` is the baseline every later change is gated against.

Layers scored now:

- ``seg_recall``: gold padas (IITK gloss line) recovered by a contiguous run of
  output tokens. Order-free, because the gloss line is in anvaya order.
- ``split_ratio``: output tokens per gold pada. Above ~1.3 means over-splitting.
- ``verify``: share of output tokens that ``prakriya.analyze_pada`` derives
  through vidyut (verify-survival).
- ``lemma_acc``: top lemma vs hand-checked lemmas. The ``reader`` engine is
  ``sanskrit_analyzer.reader`` (ByT5 hypothesis + vidyut verification).
  Its lemmas are Dhātupāṭha upadeśas for verbs (``gamx~``), so verb rows
  compare after anubandha stripping (``tests/data/corpus_verses.json``
  plus ramayanam's ``tests/eval/ramayana_deepread_gold.jsonl``).
- ``meter_acc`` / ``meter_named``: engine-independent, from ``analyze_verse``.

Layers not scored yet (need Phase 3): anvaya, word gloss, translation.

Run::

    uv run python -m tests.bench.run --ramayanam ~/Projects/ramayanam \\
        --split dev --n 100 --engines dp,prakriya --out bench.json

``--split heldout`` is measure-only. Never tune against it.
"""
from __future__ import annotations

import argparse
import json
import logging
import subprocess
import time
from collections.abc import Callable
from functools import cache
from pathlib import Path
from typing import Any

from sanskrit_analyzer.dhatu.dhatupatha import strip_anubandhas
from sanskrit_analyzer.models.scripts import Script
from sanskrit_analyzer.utils import transliterate
from tests.bench.corpus import gold_padas, load_rows, split_rows
from tests.bench.score import meter_match, norm_slp1, recovered

DATA = Path(__file__).resolve().parents[1] / "data"
PENDING_LAYERS = ("anvaya", "gloss", "translation")

# An engine maps a verse to (slp1 token, top lemma or None, verified or None).
# verified=None means "ask analyze_pada".
Token = tuple[str, str | None, bool | None]
Engine = Callable[[str], list[Token]]


def _slp1(dev: str) -> str:
    return transliterate(dev, Script.DEVANAGARI, Script.SLP1)


def _engines(names: list[str]) -> dict[str, Engine]:
    from sanskrit_analyzer.deep_read import DeepRead
    from sanskrit_analyzer.prakriya import analyze_verse

    dr = DeepRead()

    def deep(use_byt5: bool) -> Engine:
        def run(text: str) -> list[Token]:
            out: list[Token] = []
            for t in dr.analyze(text, use_byt5=use_byt5).to_dict()["tokens"]:
                slp = t.get("slp1") or _slp1(t["surface"])
                lemma = (t.get("analyses") or [{}])[0].get("lemma")
                out.append((slp, lemma, None))
            return out
        return run

    def prakriya(text: str) -> list[Token]:
        return [
            (p["surface"], p["analyses"][0]["lemma"] if p["analyses"] else None,
             bool(p["analyses"]))
            for p in analyze_verse(text)["padas"]
        ]

    def reader(text: str) -> list[Token]:
        from sanskrit_analyzer.reader.read import read_words

        out: list[Token] = []
        for w in read_words(text)[0]:
            for m in w.get("compound_members") or [w]:
                out.append((m["surface"], m["lemma"], m["verified"]))
        return out

    table = {"dp": deep(False), "byt5": deep(True), "prakriya": prakriya, "reader": reader}
    return {n: table[n] for n in names}


@cache
def _verifies(slp1: str) -> bool:
    from sanskrit_analyzer.prakriya.analyzer import analyze_pada

    word = "".join(ch for ch in slp1 if ch.isalpha() or ch == "'")
    try:
        return bool(word) and bool(analyze_pada(word, limit=1))
    except Exception:  # an engine crash is a failed verification, visibly counted
        return False


def _lemma_gold(ramayanam: Path | None) -> list[tuple[str, str, set[str]]]:
    """(verse text, gold surface slp1, accepted lemmas)."""
    gold: list[tuple[str, str, set[str]]] = []
    for case in json.loads((DATA / "corpus_verses.json").read_text()):
        for surface, lemmas in (case.get("gloss") or {}).items():
            gold.append((case["text"], surface, set(lemmas)))
    path = ramayanam / "tests/eval/ramayana_deepread_gold.jsonl" if ramayanam else None
    if path and path.exists():
        for line in path.read_text().splitlines():
            row = json.loads(line) if line.strip() else {}
            if row.get("expect_lemma"):
                gold.append((row["surface"], row["slp1"], {row["expect_lemma"]}))
    return gold


def _meter_gold() -> list[tuple[str, str]]:
    cases = json.loads((DATA / "corpus_meters.json").read_text())
    cases += [c for c in json.loads((DATA / "corpus_verses.json").read_text()) if c.get("meter")]
    return [(c["text"], c["meter"]) for c in cases]


def score_engine(fn: Engine, rows, lemma_gold) -> dict[str, Any]:
    hit = gold_n = tok_n = ver_n = 0
    t0 = time.time()
    for row in rows:
        gold = gold_padas(row.meaning)
        try:
            toks = fn(row.text)
        except Exception as exc:  # a crash scores zero for the verse, visibly
            logging.getLogger(__name__).warning("%s crashed: %s", row.ref, exc)
            toks = []
        hit += recovered(gold, [t[0] for t in toks])
        gold_n += len(gold)
        tok_n += len(toks)
        ver_n += sum(1 for slp, _, v in toks if (v if v is not None else _verifies(slp)))
    sec = (time.time() - t0) / max(len(rows), 1)

    lemma_ok = lemma_n = 0
    for text, surface, accepted in lemma_gold:
        try:
            toks = fn(text)
        except Exception:
            toks = []
        by_surface = {norm_slp1(slp): lemma for slp, lemma, _ in toks}
        lemma_n += 1
        got = by_surface.get(norm_slp1(surface))
        lemma_ok += got in accepted or (got is not None and strip_anubandhas(got) in accepted)
    return {
        "verses": len(rows),
        "seg_recall": hit / gold_n if gold_n else 0.0,
        "split_ratio": tok_n / gold_n if gold_n else 0.0,
        "verify": ver_n / tok_n if tok_n else 0.0,
        "lemma_acc": lemma_ok / lemma_n if lemma_n else 0.0,
        "lemma_n": lemma_n,
        "sec_per_verse": sec,
    }


def score_meter(rows) -> dict[str, Any]:
    from sanskrit_analyzer.prakriya import analyze_verse

    def name(text: str) -> str | None:
        try:
            ch = analyze_verse(text).get("chandas") or {}
        except Exception:
            return None
        return ch.get("name")

    gold = _meter_gold()
    ok = sum(meter_match(name(text), meter) for text, meter in gold)
    named = sum(1 for r in rows if name(r.text))
    return {
        "meter_acc": ok / len(gold),
        "meter_n": len(gold),
        "meter_named": named / len(rows) if rows else 0.0,
    }


def _git_sha() -> str:
    try:
        return subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True,
                              text=True, check=True).stdout.strip()
    except Exception:
        return "unknown"


def run(ramayanam: Path, split: str, n: int, engines: list[str], seed: int) -> dict[str, Any]:
    rows = split_rows(load_rows(ramayanam), split, n, seed)
    lemma_gold = _lemma_gold(ramayanam)
    return {
        "git": _git_sha(), "split": split, "n": len(rows), "seed": seed,
        "meter": score_meter(rows),
        "engines": {name: score_engine(fn, rows, lemma_gold)
                    for name, fn in _engines(engines).items()},
        "pending_layers": list(PENDING_LAYERS),
    }


def format_report(report: dict[str, Any]) -> str:
    m = report["meter"]
    lines = [
        f"split={report['split']} n={report['n']} seed={report['seed']} git={report['git']}",
        f"meter_acc={m['meter_acc']:.3f} (n={m['meter_n']})  meter_named={m['meter_named']:.3f}",
        f"{'engine':9} {'seg_recall':>10} {'split':>6} {'verify':>7} {'lemma':>6} {'s/verse':>8}",
    ]
    for name, e in report["engines"].items():
        lines.append(f"{name:9} {e['seg_recall']:>10.3f} {e['split_ratio']:>6.2f} "
                     f"{e['verify']:>7.3f} {e['lemma_acc']:>6.3f} {e['sec_per_verse']:>8.2f}")
    lines.append("not scored yet: " + ", ".join(report["pending_layers"]))
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    logging.disable(logging.WARNING)
    ap = argparse.ArgumentParser(prog="python -m tests.bench.run")
    ap.add_argument("--ramayanam", type=Path, required=True, help="ramayanam checkout")
    ap.add_argument("--split", choices=("dev", "heldout"), default="dev")
    ap.add_argument("--n", type=int, default=100)
    ap.add_argument("--engines", default="dp,prakriya", help="dp,byt5,prakriya,reader")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--out", type=Path)
    args = ap.parse_args(argv)
    report = run(args.ramayanam.expanduser(), args.split, args.n,
                 args.engines.split(","), args.seed)
    print(format_report(report))
    if args.out:
        args.out.write_text(json.dumps(report, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
