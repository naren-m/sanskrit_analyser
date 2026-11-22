# Reader scoreboard

One scoreboard for reader model work. Goal (naren, 2026-11-21): the best Sanskrit
reader for reading Rāmāyaṇa / Gītā verses in ramayanam. Every model PR is judged
against the **Baseline (#96 scorer)** table below (the `reader` row on Rāmāyaṇa
held-out), produced by `python -m tests.bench.run`. The legacy-scorer table further
down is kept for history only.

## Baseline (#96 scorer)

Scorer fix from #96 (PR #98), git `eb4c95e` on `main`. Checkpoint: DCS v4,
`ckpt_s30000`. Run by naren's orchestrator.

| corpus | split (data) | engine | seg_recall | split (metric) | verify | lemma | cover | agree | s/verse |
|---|---|---|---|---|---|---|---|---|---|
| Rāmāyaṇa held-out (n=60, seed 3) | heldout | reader | 0.988 | 1.231 | 0.993 | 0.909 | 0.935 | 1.000 | 15.73 |
| | heldout | reader-slm | 0.949 | 1.231 | 0.983 | 0.855 | 0.928 | 0.915 | 3.81 |
| Gītā, all chapters (n=80, seed 2) | n/a | reader | 0.911 | 0.976 | 0.993 | n/a | 0.922 | 1.000 | 13.87 |
| | n/a | reader-slm | 0.882 | 0.985 | 0.988 | n/a | 0.920 | 0.934 | 3.88 |

Commands:

    python -m tests.bench.run --ramayanam ~/Projects/ramayanam --engines reader,reader-slm --split heldout --n 60 --seed 3
    python -m tests.bench.run --ramayanam ~/Projects/ramayanam --engines reader,reader-slm --corpus gita --n 80 --seed 2

- `s/verse` was measured while a `vllm-mlx` server shared the GPU, which inflates it
  about 3-4x. Do not compare it with the legacy `s/verse` column.
- The Gītā command has no `--gita-chapters` filter (main lacks it), so those rows are
  not comparable to the legacy "Gītā 10–18" rows.
- Cross-check, `--legacy-score`, Rāmāyaṇa held-out, reader: seg_recall 0.963 -> 0.988,
  lemma 0.764 -> 0.909. The legacy numbers match the old table exactly, so only the
  scorer changed, not the engine output.

## Legacy scorer (pre-#96), for history

Checkpoint: DCS v4, `s30000`. Cascade threshold: 0.85. Source of the numbers:
`naren-m/sanskrit_model` `experiments/cascade/eval_*.txt`. These come from the scorer
before the #96 fix and undercount `lemma` and `seg_recall`. Model PRs are not judged
against this table.

Legacy scorer, DCS v4 `s30000`, cascade threshold 0.85:

| corpus | engine | seg_recall | verify | lemma | cover | agree | s/verse |
|---|---|---|---|---|---|---|---|
| Rāmāyaṇa held-out (n=60) | reader | 0.963 | 0.993 | 0.764 | 0.935 | 1.000 | 4.75 |
| | reader-slm | 0.924 | 0.983 | 0.736 | 0.928 | 0.915 | 0.93 |
| | reader-cascade (branch-only, not on main) | 0.931 | 0.991 | 0.755 | 0.929 | 0.930 | 1.29 |
| Gītā 10–18 (n=80) | reader | 0.923 | 0.991 | n/a | 0.925 | 1.000 | 4.95 |
| | reader-slm | 0.886 | 0.983 | n/a | 0.919 | 0.911 | 0.56 |
| | reader-cascade (branch-only, not on main) | 0.896 | 0.991 | n/a | 0.921 | 0.932 | 1.71 |
| Saṅgītaratnākara (n=60) | reader | n/a | 0.965 | n/a | 0.922 | 1.000 | 4.96 |
| | reader-slm | n/a | 0.966 | n/a | 0.921 | 0.873 | 0.58 |
| | reader-cascade (branch-only, not on main) | n/a | 0.965 | n/a | 0.922 | 0.880 | 1.15 |

`agree` is token F1 against `reader`. `cover` is letter similarity of input and
padas (about 0.9 for a perfect split). `n/a` means the corpus has no gold for that
column.

Other recorded runs (legacy scorer, pre-#96, Rāmāyaṇa held-out, n=60, seed 3):

| date | comparison | seg_recall | verify | lemma | note |
|---|---|---|---|---|---|
| 2026-11-21 | `reader-slm` vs constrained tagger | 0.918 vs 0.915 | 0.983 vs 0.983 | 0.736 vs 0.736 | #76, not merged |

## How each row was produced

Rows come from `sanskrit_model/experiments/cascade/eval.sh`. They ran from the
`.worktrees/slm` branch of `sanskrit_analyser`. That branch has the `reader-cascade`
engine and the `--gita-chapters` flag. **`main` has neither**, so the `reader-cascade`
rows and the `--gita-chapters 10-18` filter cannot be reproduced on main. This
scoreboard does not add them.

Env vars, set for every row:

    export PYTHONUNBUFFERED=1
    export SANSKRIT_SLM_CKPT=$HOME/Projects/sanskrit_model/data/dcs_v4/ckpt_s30000.pt
    export SANSKRIT_CASCADE_MIN_COVERAGE=0.85

Common args: `R="--ramayanam $HOME/Projects/ramayanam --engines reader,reader-slm,reader-cascade"`.

| corpus | n | seed | checkpoint | cascade threshold | command (slm branch) |
|---|---|---|---|---|---|
| Rāmāyaṇa held-out | 60 | 3 | DCS v4 `s30000` | 0.85 | `uv run --offline python -m tests.bench.run $R --split heldout --n 60 --seed 3` |
| Gītā 10–18 | 80 | 2 | DCS v4 `s30000` | 0.85 | `uv run --offline python -m tests.bench.run $R --corpus gita --gita-chapters 10-18 --n 80 --seed 2` |
| Saṅgītaratnākara | 60 | 1 | DCS v4 `s30000` | 0.85 | `uv run --offline python -m tests.bench.run $R --corpus plain --plain $HOME/Projects/sangeetaratrnakaram/verses_verified.json --n 60 --seed 1` |

On main, the Gītā command is `--corpus gita --n 80 --seed 2` with no chapter filter,
and `--engines` has no `reader-cascade` (it has `dp`, `byt5`, `prakriya`, `reader`, `reader-slm`).

## Target: when a change wins

Measured on Rāmāyaṇa held-out (`--split heldout`, measure-only, never tune on it)
against the `reader` row of the Baseline (#96 scorer) table (not the legacy table):

- `seg_recall` and `lemma` do not drop below `reader`.
- `verify` stays at or above 0.99.
- s/verse goes down.

Or the change is faster at equal quality: all of the above metrics unchanged and
s/verse lower.

## Offline smoke bench

Runs inside the test sandbox: `reader` engine only, no SLM checkpoint, no
ramayanam checkout. It reads the first `n` verses of `tests/data/corpus_verses.json`
(default 3). It is a does-it-run check,
not a scoreboard row: it has no gold padas, so `seg_recall` is `n/a`.

The report prints `proposer[reader] = {...}`, the proposer label `read_words` returned
for each verse. In the sandbox the non-slow test tier refuses model-weight loads, so
the smoke test runs the `reader` on its DP fallback (`{'dp': n}`), about 1.5 s/verse. On
a machine with the ByT5 weights it prints `{'byt5': n}` (about 7 s/verse). Only the
`byt5` run is a reader measurement.

    python -m tests.bench.run --smoke --n 3
