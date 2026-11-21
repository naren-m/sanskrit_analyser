"""SanskritBench-local: one per-layer scoreboard for verse understanding.

Phase 0 of ``naren-m/sanskrit_model: docs/plan/2026-11-13-sanskrit-understanding-plan.md``. Each row of the
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
from tests.bench.corpus import (gold_padas, load_gita, load_plain, load_rows, sample,
                                split_rows)
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

    def reader_with(proposer: str):
        def reader(text: str) -> list[Token]:
            return _reader_tokens(text, proposer)
        return reader

    def _reader_tokens(text: str, proposer: str) -> list[Token]:
        from sanskrit_analyzer.reader.read import read_words

        out: list[Token] = []
        for w in read_words(text, proposer)[0]:
            for m in w.get("compound_members") or [w]:
                out.append((m["surface"], m["lemma"], m["verified"]))
        return out

    table = {"dp": deep(False), "byt5": deep(True), "prakriya": prakriya,
             "reader": reader_with("byt5"), "reader-slm": reader_with("slm"),
             "reader-best": reader_with("best"), "reader-cascade": reader_with("cascade")}
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


def _coverage(text_dev: str, surfaces: list[str]) -> float:
    """Letter similarity between the input and the proposed padas (label-free)."""
    from sanskrit_analyzer.reader.read import coverage

    return coverage(_slp1(text_dev), [{"surface": s} for s in surfaces])


def agreement(a: list[list[str]], b: list[list[str]]) -> float:
    """Mean per-verse token F1 between two engines' outputs (label-free).

    Low agreement marks verses where at least one proposer is wrong: a cheap
    way to find hard verses in a corpus with no gold.
    """
    from collections import Counter

    scores = []
    for x, y in zip(a, b):
        cx, cy = Counter(norm_slp1(t) for t in x), Counter(norm_slp1(t) for t in y)
        hit = sum((cx & cy).values())
        scores.append(2 * hit / (sum(cx.values()) + sum(cy.values())) if hit else 0.0)
    return sum(scores) / len(scores) if scores else 0.0


def score_engine(fn: Engine, rows, lemma_gold) -> dict[str, Any]:
    hit = gold_n = tok_n = ver_n = 0
    cov: list[float] = []
    outputs: list[list[str]] = []
    t0 = time.time()
    for row in rows:
        gold = list(row.gold) if row.gold is not None else gold_padas(row.meaning)
        try:
            toks = fn(row.text)
        except Exception as exc:  # a crash scores zero for the verse, visibly
            logging.getLogger(__name__).warning("%s crashed: %s", row.ref, exc)
            toks = []
        outputs.append([t[0] for t in toks])
        cov.append(_coverage(row.text, outputs[-1]))
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
        "coverage": sum(cov) / len(cov) if cov else 0.0,
        "sec_per_verse": sec,
        "_outputs": outputs,
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


def _chapter_range(spec: str | None) -> tuple[int, int] | None:
    if not spec:
        return None
    lo, _, hi = spec.partition("-")
    return int(lo), int(hi or lo)


def _rows(corpus: str, ramayanam: Path, split: str, n: int, seed: int, plain: Path | None,
          gita_chapters: str | None = None):
    """(rows, label, has_gold). Gītā and plain corpora have no dev/heldout split:
    the DCS-trained proposer saw neither. --gita-chapters splits the Gītā for
    tuning (e.g. 1-9) versus evaluation (10-18)."""
    if corpus == "gita":
        rows = load_gita(ramayanam)
        rng = _chapter_range(gita_chapters)
        if rng:
            rows = [r for r in rows if rng[0] <= int(r.ref.split()[1].split(".")[0]) <= rng[1]]
        label = f"gita{':' + gita_chapters if gita_chapters else ''}"
        return sample(rows, n, seed), label, True
    if corpus == "plain":
        return sample(load_plain(plain), n, seed), f"plain:{plain.name}", False
    return split_rows(load_rows(ramayanam), split, n, seed), split, True


def run(ramayanam: Path, split: str, n: int, engines: list[str], seed: int,
        corpus: str = "ramayana", plain: Path | None = None,
        gita_chapters: str | None = None) -> dict[str, Any]:
    from sanskrit_analyzer.reader import read as reader_mod

    rows, label, has_gold = _rows(corpus, ramayanam, split, n, seed, plain, gita_chapters)
    lemma_gold = _lemma_gold(ramayanam) if corpus == "ramayana" else []
    scored = {}
    for name, fn in _engines(engines).items():
        reader_mod.CASCADE_STATS.clear()
        scored[name] = score_engine(fn, rows, lemma_gold)
        stats = reader_mod.CASCADE_STATS
        total = stats["slm"] + stats["fallback"]
        scored[name]["fallback_rate"] = stats["fallback"] / total if total else None
    outputs = {name: e.pop("_outputs") for name, e in scored.items()}
    first = next(iter(outputs), None)
    for name, e in scored.items():   # agreement with the first engine listed
        e["agree"] = agreement(outputs[first], outputs[name]) if name != first else 1.0
    return {
        "git": _git_sha(), "corpus": corpus, "split": label, "n": len(rows), "seed": seed,
        "has_gold": has_gold, "agree_with": first,
        "meter": score_meter(rows),
        "engines": scored,
        "pending_layers": list(PENDING_LAYERS),
    }


def format_report(report: dict[str, Any]) -> str:
    m = report["meter"]
    lines = [
        f"split={report['split']} n={report['n']} seed={report['seed']} git={report['git']}",
        f"meter_acc={m['meter_acc']:.3f} (n={m['meter_n']})  meter_named={m['meter_named']:.3f}",
        f"{'engine':12} {'seg_recall':>10} {'split':>6} {'verify':>7} {'lemma':>6} "
        f"{'cover':>6} {'agree':>6} {'s/verse':>8} {'byt5%':>6}",
    ]
    na = lambda v, ok: f"{v:.3f}" if ok else "n/a"  # noqa: E731
    gold = report.get("has_gold", True)
    for name, e in report["engines"].items():
        lines.append(f"{name:12} {na(e['seg_recall'], gold):>10} {na(e['split_ratio'], gold):>6} "
                     f"{e['verify']:>7.3f} {na(e['lemma_acc'], e['lemma_n'] > 0):>6} "
                     f"{e['coverage']:>6.3f} {e['agree']:>6.3f} {e['sec_per_verse']:>8.2f} "
                     f"{'' if e.get('fallback_rate') is None else format(e['fallback_rate'], '.0%'):>6}")
    lines.append("byt5% = share of verses where the cascade called ByT5. "
                 f"agree = token F1 against '{report.get('agree_with')}'. "
                 "cover = letter similarity of input and padas (~0.9 for a perfect split).")
    lines.append("not scored yet: " + ", ".join(report["pending_layers"]))
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    logging.disable(logging.WARNING)
    ap = argparse.ArgumentParser(prog="python -m tests.bench.run")
    ap.add_argument("--ramayanam", type=Path, required=True, help="ramayanam checkout")
    ap.add_argument("--split", choices=("dev", "heldout"), default="dev")
    ap.add_argument("--n", type=int, default=100)
    ap.add_argument("--engines", default="dp,prakriya", help="dp,byt5,prakriya,reader,reader-slm,reader-best "
                    "(reader-slm/-best need SANSKRIT_SLM_CKPT)")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--corpus", choices=("ramayana", "gita", "plain"), default="ramayana",
                    help="gita: ramayanam's gita pack (gold = gita/gita word keys). "
                         "plain: --plain JSON with no gold (label-free metrics only)")
    ap.add_argument("--plain", type=Path, help='JSON list with a "devanagari" field')
    ap.add_argument("--gita-chapters", help="e.g. 1-9 (tune the cascade) or 10-18 (evaluate)")
    ap.add_argument("--out", type=Path)
    args = ap.parse_args(argv)
    if args.corpus == "plain" and not args.plain:
        ap.error("--corpus plain needs --plain <file.json>")
    report = run(args.ramayanam.expanduser(), args.split, args.n, args.engines.split(","),
                 args.seed, args.corpus, args.plain.expanduser() if args.plain else None,
                 args.gita_chapters)
    print(format_report(report))
    if args.out:
        args.out.write_text(json.dumps(report, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
