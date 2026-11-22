"""SanskritBench-local: one per-layer scoreboard for verse understanding.

Phase 0 of
``naren-m/sanskrit_model: docs/plan/2026-11-13-sanskrit-understanding-plan.md``.
Each row of the report is one engine; each column is one layer of understanding. The first run
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

Offline smoke (no corpus checkout, no SLM checkpoint, ``reader`` engine only,
well under a minute; the report prints which proposer ran)::

    uv run python -m tests.bench.run --smoke --n 3

The scoreboard and the win rule live in ``tests/bench/SCOREBOARD.md``.
"""
from __future__ import annotations

import argparse
import json
import logging
import subprocess
import sys
import time
from collections import Counter
from collections.abc import Callable
from functools import cache
from pathlib import Path
from typing import Any

from sanskrit_analyzer.dhatu.dhatupatha import strip_anubandhas
from sanskrit_analyzer.models.scripts import Script
from sanskrit_analyzer.utils import transliterate
from tests.bench.corpus import (
    Row,
    clean_verse,
    gold_padas,
    load_gita,
    load_plain,
    load_rows,
    sample,
    split_rows,
)
from tests.bench.score import lemma_match, meter_match, norm_slp1, recovered

logger = logging.getLogger(__name__)

DATA = Path(__file__).resolve().parents[1] / "data"
PROPOSERS_RAN: Counter[str] = Counter()  # proposer label read_words reported, per read
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
        words, ran = read_words(text, proposer)
        PROPOSERS_RAN[ran] += 1
        for w in words:
            for m in w.get("compound_members") or [w]:
                out.append((m["surface"], m["lemma"], m["verified"]))
        return out

    table = {"dp": deep(False), "byt5": deep(True), "prakriya": prakriya,
             "reader": reader_with("byt5"), "reader-slm": reader_with("slm"),
             "reader-best": reader_with("best")}
    return {n: table[n] for n in names}


@cache
def _verifies(slp1: str) -> bool:
    from sanskrit_analyzer.prakriya.analyzer import analyze_pada

    word = "".join(ch for ch in slp1 if ch.isalpha() or ch == "'")
    try:
        return bool(word) and bool(analyze_pada(word, limit=1))
    except Exception:  # an engine crash is a failed verification, visibly counted
        logger.debug("analyze_pada crashed on %r", word, exc_info=True)
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


def score_engine(fn: Engine, rows, lemma_gold, legacy: bool = False) -> dict[str, Any]:
    """Score one engine. ``legacy`` also reports the pre-#96 scorer's numbers
    (``seg_recall_legacy``, ``lemma_acc_legacy``) from the same engine output."""
    hit = hit_old = gold_n = tok_n = ver_n = 0
    cov: list[float] = []
    outputs: list[list[str]] = []
    t0 = time.time()
    for row in rows:
        gold = list(row.gold) if row.gold is not None else gold_padas(row.meaning)
        try:
            toks = fn(row.text)
        except Exception as exc:  # a crash scores zero for the verse, visibly
            logger.warning("%s crashed: %s", row.ref, exc)
            toks = []
        outputs.append([t[0] for t in toks])
        cov.append(_coverage(row.text, outputs[-1]))
        hit += recovered(gold, [t[0] for t in toks])
        hit_old += recovered(gold, [t[0] for t in toks], legacy=True) if legacy else 0
        gold_n += len(gold)
        tok_n += len(toks)
        ver_n += sum(1 for slp, _, v in toks if (v if v is not None else _verifies(slp)))
    sec = (time.time() - t0) / max(len(rows), 1)

    lemma_ok = lemma_old = lemma_n = 0
    for text, surface, accepted in lemma_gold:
        try:
            toks = fn(text)
        except Exception:
            logger.debug("engine crashed on %r", text, exc_info=True)
            toks = []
        lemma_n += 1
        lemma_ok += lemma_match(surface, [(slp, lemma) for slp, lemma, _ in toks], accepted)
        if legacy:
            by_surface = {norm_slp1(slp, True): lemma for slp, lemma, _ in toks}
            got = by_surface.get(norm_slp1(surface, True))
            lemma_old += got in accepted or (got is not None and strip_anubandhas(got) in accepted)
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
        **({"seg_recall_legacy": hit_old / gold_n if gold_n else 0.0,
            "lemma_acc_legacy": lemma_old / lemma_n if lemma_n else 0.0} if legacy else {}),
    }


def score_meter(rows) -> dict[str, Any]:
    from sanskrit_analyzer.prakriya import analyze_verse

    def name(text: str) -> str | None:
        try:
            ch = analyze_verse(text).get("chandas") or {}
        except Exception:
            logger.debug("analyze_verse crashed on %r", text, exc_info=True)
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
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def _rows(corpus: str, ramayanam: Path, split: str, n: int, seed: int, plain: Path | None):
    """(rows, label, has_gold). Gītā and plain corpora have no dev/heldout split:
    the DCS-trained proposer saw neither, and nothing here was tuned on them."""
    if corpus == "gita":
        return sample(load_gita(ramayanam), n, seed), "gita", True
    if corpus == "plain":
        return sample(load_plain(plain), n, seed), f"plain:{plain.name}", False
    return split_rows(load_rows(ramayanam), split, n, seed), split, True


def smoke_rows(n: int) -> list[Row]:
    """First ``n`` verses of the committed ``corpus_verses.json``: no gold padas."""
    cases = json.loads((DATA / "corpus_verses.json").read_text())[:n]
    return [Row(c["ref"], 0, clean_verse(c["text"]), "", "", ()) for c in cases]


def run_smoke(n: int, engines: list[str] | None = None) -> dict[str, Any]:
    """Score the offline ``reader`` engine on the committed verses (label-free
    metrics plus the hand-checked lemmas of those verses)."""
    cases = json.loads((DATA / "corpus_verses.json").read_text())[:n]
    texts = {c["text"] for c in cases}
    lemma_gold = [g for g in _lemma_gold(None) if g[0] in texts]
    rows = smoke_rows(n)
    # The lemma pass re-reads each verse once per gold word: cache the reads.
    scored = {}
    for name, fn in _engines(engines or ["reader"]).items():
        PROPOSERS_RAN.clear()
        scored[name] = score_engine(cache(fn), rows, lemma_gold)
        # Which proposer actually ran: "dp" means the ByT5 load failed (or was
        # refused by the non-slow weight guard) and the reader fell back.
        scored[name]["proposers"] = dict(PROPOSERS_RAN)
    for e in scored.values():
        e.pop("_outputs")
        e["agree"] = 1.0
    return {
        "git": _git_sha(), "corpus": "smoke", "split": "smoke", "n": len(rows), "seed": 0,
        "has_gold": False, "agree_with": next(iter(scored)),
        "meter": score_meter(rows), "engines": scored,
        "pending_layers": list(PENDING_LAYERS),
    }


def run(ramayanam: Path, split: str, n: int, engines: list[str], seed: int,
        corpus: str = "ramayana", plain: Path | None = None,
        legacy: bool = False) -> dict[str, Any]:
    rows, label, has_gold = _rows(corpus, ramayanam, split, n, seed, plain)
    lemma_gold = _lemma_gold(ramayanam) if corpus == "ramayana" else []
    scored = {name: score_engine(fn, rows, lemma_gold, legacy) for name, fn in _engines(engines).items()}
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
        f"{'cover':>6} {'agree':>6} {'s/verse':>8}",
    ]
    na = lambda v, ok: f"{v:.3f}" if ok else "n/a"  # noqa: E731
    gold = report.get("has_gold", True)
    for name, e in report["engines"].items():
        lines.append(f"{name:12} {na(e['seg_recall'], gold):>10} {na(e['split_ratio'], gold):>6} "
                     f"{e['verify']:>7.3f} {na(e['lemma_acc'], e['lemma_n'] > 0):>6} "
                     f"{e['coverage']:>6.3f} {e['agree']:>6.3f} {e['sec_per_verse']:>8.2f}")
    for name, e in report["engines"].items():
        if "proposers" in e:
            lines.append(f"proposer[{name}] = {e['proposers']}")
        if "seg_recall_legacy" in e:
            lines.append(f"legacy scorer {name}: seg_recall {e['seg_recall_legacy']:.3f} -> "
                         f"{e['seg_recall']:.3f}, lemma {e['lemma_acc_legacy']:.3f} -> "
                         f"{e['lemma_acc']:.3f}")
    lines.append(f"agree = token F1 against '{report.get('agree_with')}'. "
                 "cover = letter similarity of input and padas (~0.9 for a perfect split).")
    lines.append("not scored yet: " + ", ".join(report["pending_layers"]))
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    logging.disable(logging.WARNING)
    ap = argparse.ArgumentParser(prog="python -m tests.bench.run")
    ap.add_argument("--ramayanam", type=Path, help="ramayanam checkout (not needed with --smoke)")
    ap.add_argument("--smoke", action="store_true",
                    help=("offline: reader engine only, first --n verses of "
                          "tests/data/corpus_verses.json"))
    ap.add_argument("--split", choices=("dev", "heldout"), default="dev")
    ap.add_argument("--n", type=int, help="verses (default 100; 3 with --smoke)")
    ap.add_argument("--engines", default="dp,prakriya",
                    help="dp,byt5,prakriya,reader,reader-slm,reader-best "
                    "(reader-slm/-best need SANSKRIT_SLM_CKPT)")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--corpus", choices=("ramayana", "gita", "plain"), default="ramayana",
                    help="gita: ramayanam's gita pack (gold = gita/gita word keys). "
                         "plain: --plain JSON with no gold (label-free metrics only)")
    ap.add_argument("--plain", type=Path, help='JSON list with a "devanagari" field')
    ap.add_argument("--legacy-score", action="store_true",
                    help="also print the pre-#96 seg_recall and lemma_acc, old -> new")
    ap.add_argument("--out", type=Path)
    args = ap.parse_args(argv)
    if args.smoke:
        report = run_smoke(args.n or 3)
        sys.stdout.write(format_report(report) + "\n")
        if args.out:
            args.out.write_text(json.dumps(report, indent=2, ensure_ascii=False))
        return 0
    if not args.ramayanam:
        ap.error("--ramayanam is required unless --smoke")
    if args.corpus == "plain" and not args.plain:
        ap.error("--corpus plain needs --plain <file.json>")
    report = run(args.ramayanam.expanduser(), args.split, args.n or 100, args.engines.split(","),
                 args.seed, args.corpus, args.plain.expanduser() if args.plain else None,
                 args.legacy_score)
    sys.stdout.write(format_report(report) + "\n")
    if args.out:
        args.out.write_text(json.dumps(report, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
