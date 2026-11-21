# Reader scoreboard

One scoreboard for reader model work. Goal (naren, 2026-11-21): the best Sanskrit
reader for reading Rāmāyaṇa / Gītā verses in ramayanam. Every model PR is judged
against the numbers below, produced by `python -m tests.bench.run`.

## Baseline

Checkpoint: DCS v4, `s30000`. Cascade threshold: 0.85. Source of the numbers:
`naren-m/sanskrit_model` `experiments/cascade/eval_*.txt`.

> **Scorer caveat.** These numbers come from the scorer before the fix tracked in
> #96. Per naren, `lemma` (0.764) and `seg_recall` (0.963) undercount: every lemma
> miss is a compound/visarga/nasal matching artifact. **Re-record this table with
> the #96 scorer before any model PR is judged against it.**

| corpus | engine | seg_recall | verify | lemma | cover | agree | s/verse |
|---|---|---|---|---|---|---|---|
| Rāmāyaṇa held-out (n=60) | reader | 0.963 | 0.993 | 0.764 | 0.935 | 1.000 | 4.75 |
| | reader-slm | 0.924 | 0.983 | 0.736 | 0.928 | 0.915 | 0.93 |
| | reader-cascade | 0.931 | 0.991 | 0.755 | 0.929 | 0.930 | 1.29 |
| Gītā 10–18 (n=80) | reader | 0.923 | 0.991 | n/a | 0.925 | 1.000 | 4.95 |
| | reader-slm | 0.886 | 0.983 | n/a | 0.919 | 0.911 | 0.56 |
| | reader-cascade | 0.896 | 0.991 | n/a | 0.921 | 0.932 | 1.71 |
| Saṅgītaratnākara (n=60) | reader | n/a | 0.965 | n/a | 0.922 | 1.000 | 4.96 |
| | reader-slm | n/a | 0.966 | n/a | 0.921 | 0.873 | 0.58 |
| | reader-cascade | n/a | 0.965 | n/a | 0.922 | 0.880 | 1.15 |

`agree` is token F1 against `reader`. `cover` is letter similarity of input and
padas (about 0.9 for a perfect split). `n/a` means the corpus has no gold for that
column.

## How each row was produced

Rows come from `sanskrit_model/experiments/cascade/eval.sh`, which this repo's
tooling cannot read. Only the facts stated in issue #87 are recorded here.
`reader-cascade` is not an engine in `tests/bench/run.py` on `main`.

| corpus | n | split / seed | checkpoint | cascade threshold | command and env vars |
|---|---|---|---|---|---|
| Rāmāyaṇa held-out | 60 | `--split heldout` / TODO(naren) | DCS v4 `s30000` | 0.85 | TODO(naren): from sanskrit_model eval.sh |
| Gītā 10–18 | 80 | `--corpus gita` / TODO(naren) | DCS v4 `s30000` | 0.85 | TODO(naren): from sanskrit_model eval.sh |
| Saṅgītaratnākara | 60 | `--corpus plain` / TODO(naren) | DCS v4 `s30000` | 0.85 | TODO(naren): from sanskrit_model eval.sh |

The shape of each command is
`python -m tests.bench.run --ramayanam <checkout> [--split heldout | --corpus gita | --corpus plain --plain <file.json>] --n <n> --seed <seed> --engines reader,reader-slm`
with `SANSKRIT_SLM_CKPT` pointing at the checkpoint for the SLM engines.

## Target: when a change wins

Measured on Rāmāyaṇa held-out (`--split heldout`, measure-only, never tune on it)
against the `reader` row:

- `seg_recall` and `lemma` do not drop below `reader`.
- `verify` stays at or above 0.99.
- s/verse goes down.

Or the change is faster at equal quality: all of the above metrics unchanged and
s/verse lower.

## Offline smoke bench

Runs inside the test sandbox: `reader` engine only, no SLM checkpoint, no
ramayanam checkout. It reads the first `n` verses of `tests/data/corpus_verses.json`
(default 3, about 35 s with the ByT5 weights loaded). It is a does-it-run check,
not a scoreboard row: it has no gold padas, so `seg_recall` is `n/a`.

    python -m tests.bench.run --smoke --n 3
