# Dhātu Resolution Migration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `sanskrit_analyzer` the single owner of Dhātupāṭha rule data and verbal-root (dhātu) resolution, so every consumer gets one correct implementation instead of three partial ones.

**Architecture:** The root-resolution logic currently lives in `yoga_sutras/backend/app/services/dhatu_resolver.py`, which reaches into a *sibling checkout* of `sanskrit_model` via `sys.path.insert` to borrow `strip_anubandhas` and `DhatuKosha`. Meanwhile `sanskrit_analyzer` has its own weaker implementation (`dhatu/identifier.py`). This plan moves the Dhātupāṭha data and both algorithms into `sanskrit_analyzer/dhatu/`, fixes the anubandha-stripping defects at their source, points `sanskrit_model` at the analyzer for those two symbols, and cuts `yoga_sutras` over to the shared implementation while keeping its Monier-Williams etymology as an injected hook.

**Tech Stack:** Python ≥3.10, `vidyut` (Kośa + Dhātupāṭha bundle), `indic-transliteration`, stdlib `csv`/`re`, pytest, hatchling.

## Global Constraints

- Target Python is **≥3.10** (`requires-python = ">=3.10"`, ruff `target-version = "py310"`). Do not use 3.11+ syntax. `X | None` annotations are fine only with `from __future__ import annotations` at the top of every new module.
- Ruff: `line-length = 100`, lint rules `["E", "F", "I", "N", "W", "UP"]`.
- mypy runs with `disallow_untyped_defs = true`, `disallow_incomplete_defs = true`, `strict_optional = true`. **Every function and method you add needs full type annotations**, including `-> None`. The code being ported from `sanskrit_model` and `yoga_sutras` is only partially annotated — annotate as you port.
- pytest: `testpaths = ["tests"]`, `asyncio_mode = "auto"`. A `slow` marker exists for tests needing ML weights — use it for anything touching ByT5.
- Packaging is hatchling with `packages = ["sanskrit_analyzer"]`. Any file placed inside the `sanskrit_analyzer/` package directory ships in the wheel automatically; no `package-data` stanza is needed.
- Data files are located with `Path(__file__).parent / "name"` — follow the existing precedent at `sanskrit_analyzer/data/dhatu_db.py:57`. Do **not** introduce `importlib.resources`.
- Everything must degrade gracefully when the vidyut data bundle is absent: resolution returns `None`, never raises. This is load-bearing for consumers whose CI has no bundle.
- Do not delete `sanskrit_analyzer/data/comprehensive_dhatu_database.db` or `data/dhatu_db.py`. They are a separate, lower-coverage lookup with their own consumers; this plan adds alongside them.

## Background: the four defects being fixed

Measured against the 31-term golden set (`yoga_sutras/backend/tests/test_dhatu_golden_terms.py`), the analyzer's current `DhatuIdentifier` scores **10/31 (32%)** and the yoga_sutras resolver scores **29/31 (94%)**. The analyzer's failures are systematic:

1. **Anubandha residue leaks into output.** It reads `dhatu_entry.clean_text` from vidyut, which is not reliably clean: योगः → `yoji`, विषयम् → `vizevi`, क्लेश → `kleSi`. None of those are roots.
2. **No upasarga peeling.** अभिनिवेश → `aBiniveSi` instead of `viS`; संस्कार → `saMskAri` instead of `kf`.
3. **Homograph misranking.** हानम् → `han` ("to kill") instead of `hA` ("to abandon") — semantically inverted in a philosophical text.
4. **`strip_anubandhas` itself is wrong in two directions** (this is upstream of defects 1–2, in `sanskrit_model/slm/rules.py:536`):
   - Over-strips: `_IT_PREFIX_CLUSTERS` includes `"Gu"`, mangling **11 real roots** whose own initial is *ghu-* (√ghuṇ, √ghūrṇ, √ghuṣ) — 7 of them all the way down to a single consonant. `GuRa~` → `"R"`.
   - Under-strips: the list omits `Yi` (ñi, **14 roots**) and the leading ovit marker `o~` (**12 roots**). `o~hA\k` → `"o~hA"`, and a downstream trailing-residue rule then eats the root entirely, leaving `"o"` — which is why √hā was unreachable and हानम् fell through to √han.
   - `Qu` and `Wu` are in the list but match **0 rows** in `dhatus-full.csv`.

The `yoga_sutras` resolver works around 4 downstream. This plan fixes it at source.

## File Structure

**Created in `sanskrit_analyzer`:**

| Path | Responsibility |
|---|---|
| `sanskrit_analyzer/dhatu/dhatupatha.py` | `strip_anubandhas()` + `DhatuKosha` — Dhātupāṭha CSV index and it-marker stripping. Pure stdlib. |
| `sanskrit_analyzer/data/dhatus-full.csv` | 2259 Dhātupāṭha roots (moved from `sanskrit_model/dhatus-full.csv`, 206K). |
| `sanskrit_analyzer/data/dhatus-core.csv` | 294 hand-curated clean roots (moved from `sanskrit_model/dhatus-core.csv`, 28K). |
| `sanskrit_analyzer/dhatu/resolver.py` | `DhatuResolver` — stem/word → root via vidyut Kośa, with ranking, prefix peeling, citation-spelling normalization. |
| `tests/test_dhatu/test_dhatupatha.py` | Unit tests for stripping and index lookup. |
| `tests/test_dhatu/test_resolver.py` | Unit tests for resolution, ranking, peeling. |
| `tests/test_dhatu/test_golden_terms.py` | The 31-term golden regression suite, moved up from yoga_sutras. |

**Modified in `sanskrit_analyzer`:**

| Path | Change |
|---|---|
| `sanskrit_analyzer/dhatu/identifier.py` | `DhatuIdentifier` delegates root extraction to `DhatuResolver`; gains a `preferred_root_fn` injection hook. |
| `sanskrit_analyzer/dhatu/__init__.py` | Export `DhatuResolver`, `DhatuKosha`, `strip_anubandhas`. |

**Modified in `sanskrit_model`:**

| Path | Change |
|---|---|
| `slm/rules.py` | Delete `strip_anubandhas` + `DhatuKosha` + `_IT_PREFIX_CLUSTERS`; re-export from the analyzer so all five existing call sites keep working unchanged. |
| `pyproject.toml` | Add `sanskrit-analyzer` dependency. |
| `dhatus-full.csv`, `dhatus-core.csv` | Deleted (now owned by the analyzer). |

**Modified in `yoga_sutras`:**

| Path | Change |
|---|---|
| `backend/app/services/dhatu_resolver.py` | **Deleted.** |
| `backend/app/services/sanskrit_adapter.py` | Import the resolver from the analyzer; inject MW `_cited_root` via the hook. |
| `backend/tests/test_dhatu_resolver.py`, `backend/tests/test_dhatu_golden_terms.py` | **Deleted** (moved upstream). |

**Dependency direction check:** `sanskrit_analyzer` does not import `sanskrit_model` anywhere today (verified by grep), so adding `sanskrit_model → sanskrit_analyzer` introduces **no cycle**.

---

### Task 1: Move the Dhātupāṭha data and stripping into the analyzer, behavior unchanged

This task is a **pure move**. It deliberately does *not* fix the defects — the tests written here pin current behavior so that Task 2's fixes are visibly attributable. Resist the urge to fix `Gu` here.

**Files:**
- Create: `sanskrit_analyzer/dhatu/dhatupatha.py`
- Create: `sanskrit_analyzer/data/dhatus-full.csv` (copy of `~/Projects/sanskrit_model/dhatus-full.csv`)
- Create: `sanskrit_analyzer/data/dhatus-core.csv` (copy of `~/Projects/sanskrit_model/dhatus-core.csv`)
- Test: `tests/test_dhatu/test_dhatupatha.py`

**Interfaces:**
- Consumes: nothing from earlier tasks.
- Produces:
  - `strip_anubandhas(upadesha: str) -> str`
  - `class DhatuKosha` with `__init__(self, full_path: str | Path | None = None, core_path: str | Path | None = None) -> None`, attribute `entries: list[dict[str, Any]]`, and methods `lookup(self, root: str) -> list[dict[str, Any]]`, `by_gana(self, gana: int) -> list[dict[str, Any]]`, `all_roots(self) -> list[str]`.
  - Each entry dict carries the CSV columns (`code`, `dhatu_slp1`, `dhatu_iast`, `gana`, `artha_iast`, `artha_slp1`, …) plus `core_root: str` and `curated: bool`.

- [ ] **Step 1: Copy the two CSVs into the analyzer's data directory**

```bash
cd ~/Projects/sanskrit_analyzer
cp ~/Projects/sanskrit_model/dhatus-full.csv sanskrit_analyzer/data/dhatus-full.csv
cp ~/Projects/sanskrit_model/dhatus-core.csv sanskrit_analyzer/data/dhatus-core.csv
wc -l sanskrit_analyzer/data/dhatus-*.csv
```

Expected: `dhatus-full.csv` has 2260 lines (2259 rows + header), `dhatus-core.csv` has 295 lines (294 + header).

- [ ] **Step 2: Write the failing test**

Create `tests/test_dhatu/test_dhatupatha.py`:

```python
"""Dhatupatha index and it-marker stripping.

These tests pin the behaviour as moved from sanskrit_model, including two
known-wrong cases (see test_known_defects_pinned) that Task 2 fixes.
"""

from sanskrit_analyzer.dhatu.dhatupatha import DhatuKosha, strip_anubandhas


def test_strips_accent_marks():
    assert strip_anubandhas("yu\\ja~") == "yuj"


def test_strips_leading_du_marker():
    """ḍukṛñ is √kṛ — the ḍu- is a recitation-list marker."""
    assert strip_anubandhas("qukf\\Y") == "kf"


def test_strips_trailing_nasal_marker_and_its_vowel():
    assert strip_anubandhas("Bava~") == "Bav"


def test_kosha_loads_every_row():
    kosha = DhatuKosha()
    assert len(kosha.entries) == 2259


def test_kosha_prefers_curated_core_root():
    kosha = DhatuKosha()
    curated = [e for e in kosha.entries if e["curated"]]
    assert len(curated) > 0
    assert all(e["core_root"] for e in curated)


def test_lookup_finds_a_common_root():
    kosha = DhatuKosha()
    assert kosha.lookup("gam")


def test_by_gana_filters():
    kosha = DhatuKosha()
    first_gana = kosha.by_gana(1)
    assert first_gana
    assert all(int(e["gana"]) == 1 for e in first_gana)


def test_known_defects_pinned():
    """Behaviour that is WRONG but is being moved unchanged; Task 2 fixes it.

    √ghuṇ loses its own initial ghu- (read as a marker), and the ovit marker
    o~ of √hā is not recognised as leading at all.
    """
    assert strip_anubandhas("GuRa~") == "R"
    assert strip_anubandhas("o~hA\\k") == "o~hA"
    assert strip_anubandhas("YiPalA~") == "YiPal"
```

- [ ] **Step 3: Run the test to verify it fails**

Run: `cd ~/Projects/sanskrit_analyzer && python -m pytest tests/test_dhatu/test_dhatupatha.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'sanskrit_analyzer.dhatu.dhatupatha'`

- [ ] **Step 4: Create the module**

Create `sanskrit_analyzer/dhatu/dhatupatha.py`. Copy `VOWELS`, `CONSONANTS`, `_IT_PREFIX_CLUSTERS`, `strip_anubandhas`, and `DhatuKosha` verbatim from `~/Projects/sanskrit_model/slm/rules.py` (lines 536–640), then apply exactly three mechanical changes: repoint the data paths, add the missing type annotations, and keep the docstrings.

```python
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
from pathlib import Path
from typing import Any

_DATA_DIR = Path(__file__).resolve().parent.parent / "data"

VOWELS: set[str] = set("aAiIuUfFxXeEoO")
CONSONANTS: set[str] = set("kKgGNcCjJYwWqQRtTdDnpPbBmyrlvSzsh")

#: Traditional Dhātupāṭha "cutu" it-clusters conventionally prefixed to a
#: root purely to disambiguate it in the recitation list (e.g. "qukfY" for
#: kf, "quBf\\Y" for Bf).
_IT_PREFIX_CLUSTERS = ("qu", "wu", "Qu", "Wu", "Gu")


def strip_anubandhas(upadesha: str) -> str:
    """Strip Pāṇinian it-markers from a dhātu's upadeśa (citation) form.

    Deliberately NOT a full implementation of the it-saṃjñā sūtras
    (Aṣṭādhyāyī 1.3.2-1.3.9), which require per-root knowledge of which
    letters are markers versus real phonemes — that is why dhatus-core.csv
    exists as a hand-curated table. Callers should prefer the curated
    ``core_root`` when a root is in it; this is the fallback for the rest.
    """
    s = upadesha.replace("^", "").replace("\\", "")

    for prefix in _IT_PREFIX_CLUSTERS:
        if s.startswith(prefix) and len(s) > len(prefix) + 1:
            s = s[len(prefix):]
            break

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

    def by_gana(self, gana: int) -> list[dict[str, Any]]:
        """Every entry in a given gaṇa (1-10)."""
        return [e for e in self.entries if int(e["gana"]) == int(gana)]

    def all_roots(self) -> list[str]:
        """Return the sorted set of unique resolved clean roots."""
        return sorted({e["core_root"] for e in self.entries})
```

`VOWELS` and `CONSONANTS` are `set[str]` in the original (`slm/rules.py:58,68`) and are reproduced exactly above — do not "simplify" them to plain strings, since `strip_anubandhas` does membership tests against them and other analyzer code may import them.

- [ ] **Step 5: Run the tests to verify they pass**

Run: `cd ~/Projects/sanskrit_analyzer && python -m pytest tests/test_dhatu/test_dhatupatha.py -v`
Expected: PASS, 8 tests.

- [ ] **Step 6: Run lint and types on the new module**

```bash
cd ~/Projects/sanskrit_analyzer
ruff check sanskrit_analyzer/dhatu/dhatupatha.py
mypy sanskrit_analyzer/dhatu/dhatupatha.py
```
Expected: both clean.

- [ ] **Step 7: Commit**

```bash
cd ~/Projects/sanskrit_analyzer
git add sanskrit_analyzer/dhatu/dhatupatha.py sanskrit_analyzer/data/dhatus-full.csv \
        sanskrit_analyzer/data/dhatus-core.csv tests/test_dhatu/test_dhatupatha.py
git commit -m "feat(dhatu): own the Dhatupatha index and anubandha stripping"
```

---

### Task 2: Fix the it-marker defects at source

**Files:**
- Modify: `sanskrit_analyzer/dhatu/dhatupatha.py`
- Test: `tests/test_dhatu/test_dhatupatha.py`

**Interfaces:**
- Consumes: `strip_anubandhas`, `DhatuKosha` from Task 1.
- Produces: same signatures. Behaviour changes only for the 37 affected roots; `core_root` values for uncurated `Gu`/`Yi`/`o~` rows change.

**Evidence for each change** (counts from `dhatus-full.csv`, verify with the script in Step 1):

| cluster | rows | correct treatment |
|---|---|---|
| `qu` (ḍu) | 10 | strip — genuine marker |
| `wu` (ṭu) | 12 | strip — genuine marker |
| `Yi` (ñi) | 14 | **strip — genuine marker, currently missed** |
| `o~` (ovit) | 12 | **strip — leading marker, currently missed** |
| `Gu` | 11 | **do NOT strip — √ghuṇ/√ghūrṇ/√ghuṣ own their ghu-** |
| `Qu`, `Wu` | 0 | remove — match nothing |

- [ ] **Step 1: Confirm the counts before changing anything**

```bash
cd ~/Projects/sanskrit_analyzer && python - <<'EOF'
import csv, collections
rows = list(csv.DictReader(open("sanskrit_analyzer/data/dhatus-full.csv", encoding="utf-8")))
c = collections.defaultdict(list)
for r in rows:
    d = r["dhatu_slp1"]
    for p in ("qu", "wu", "Qu", "Wu", "Gu", "Yi"):
        if d.startswith(p):
            c[p].append((d, r["dhatu_iast"]))
    if d.startswith("o~") or "o~" in d[:4]:
        c["o~"].append((d, r["dhatu_iast"]))
for p in ("qu", "wu", "Qu", "Wu", "Gu", "Yi", "o~"):
    print(f"{p:4} {len(c.get(p, [])):3}  {c.get(p, [])[:3]}")
EOF
```
Expected: `qu 10`, `wu 12`, `Qu 0`, `Wu 0`, `Gu 11`, `Yi 14`, `o~ 12`. If any count differs, stop and reconcile before proceeding — the CSV has changed since this plan was written.

- [ ] **Step 2: Write the failing tests**

Replace `test_known_defects_pinned` in `tests/test_dhatu/test_dhatupatha.py` with:

```python
def test_ghu_initial_roots_keep_their_own_initial():
    """√ghuṇ 'to turn', √ghuṣ 'to sound': the ghu- is the root, not a marker.

    Eleven roots were being reduced to a single consonant by treating it as
    a cutu it-cluster.
    """
    assert strip_anubandhas("GuRa~") == "GuR"
    assert strip_anubandhas("Guwa~") == "Guw"
    assert strip_anubandhas("Guzi~\\") == "Guz"


def test_strips_leading_nyi_marker():
    """ñiphalā is √phal; ñi- is a recitation marker like ḍu- and ṭu-."""
    assert strip_anubandhas("YiPalA~") == "Pal"


def test_strips_leading_ovit_marker():
    """ohāk is √hā 'to abandon'. Leaving the o~ on caused it to be lost."""
    assert strip_anubandhas("o~hA\\k") == "hA"
    assert strip_anubandhas("o~vijI~\\") == "vij"


def test_strips_stacked_leading_markers():
    """ṭuosphūrjā carries both ṭu- and o~."""
    assert strip_anubandhas("wuo~sPUrjA~") == "sPUrj"


def test_no_root_reduces_to_a_bare_consonant():
    """A single consonant is never a Sanskrit root; single vowels (√i, √ṛ) are.

    Seven roots collapsed this way before the fix, all of the ghu- family.
    The dhatus-full.csv has 30 rows whose dhatu_slp1 is a literal "-"
    placeholder — those are not roots and are excluded.
    """
    kosha = DhatuKosha()
    bad = [
        e for e in kosha.entries
        if e["dhatu_slp1"] != "-"
        and len(e["core_root"]) == 1
        and e["core_root"] not in VOWELS
    ]
    assert bad == [], f"{len(bad)} roots collapsed to a bare consonant"


def test_hā_is_reachable_by_its_clean_root():
    """The whole point: √hā must be findable, or hānam falls to √han."""
    assert DhatuKosha().lookup("hA")
```

Add `VOWELS` to the import line at the top of the test file:

```python
from sanskrit_analyzer.dhatu.dhatupatha import VOWELS, DhatuKosha, strip_anubandhas
```

- [ ] **Step 3: Run the tests to verify they fail**

Run: `python -m pytest tests/test_dhatu/test_dhatupatha.py -v`
Expected: FAIL on `test_ghu_initial_roots_keep_their_own_initial` (`assert 'R' == 'GuR'`), `test_strips_leading_nyi_marker`, `test_strips_leading_ovit_marker`, `test_strips_stacked_leading_markers`, and `test_no_root_reduces_to_a_bare_consonant`.

- [ ] **Step 4: Implement the fix**

In `sanskrit_analyzer/dhatu/dhatupatha.py`, replace the `_IT_PREFIX_CLUSTERS` constant and the prefix loop inside `strip_anubandhas`:

```python
#: Traditional Dhātupāṭha it-clusters prefixed to a root purely to
#: disambiguate it in the recitation list: ḍukṛñ is √kṛ, ñiṣvapa is √svap.
#: "Gu" is deliberately absent — eleven roots (√ghuṇ, √ghūrṇ, √ghuṣ ...) own
#: that ghu- as their own initial, and stripping it left a bare consonant.
_IT_PREFIX_CLUSTERS = ("qu", "wu", "Yi")

#: The ovit marker, written with a tilde of its own and standing before the
#: root (ohāk = √hā). It may follow another cluster: ṭuosphūrjā.
_IT_PREFIX_OVIT = "o~"
```

and in `strip_anubandhas`, replace the single prefix loop with a loop that peels repeatedly, so stacked markers come off:

```python
    s = upadesha.replace("^", "").replace("\\", "")

    # Leading markers may stack (ṭu + o~ + sphūrj), so peel until none match.
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
```

Leave steps 3 and 4 of the function (the trailing-`~` and trailing-consonant rules) exactly as they are.

- [ ] **Step 5: Run the tests to verify they pass**

Run: `python -m pytest tests/test_dhatu/test_dhatupatha.py -v`
Expected: PASS, all tests.

- [ ] **Step 6: Measure the change against the curated ground truth**

```bash
cd ~/Projects/sanskrit_analyzer && python - <<'EOF'
from sanskrit_analyzer.dhatu.dhatupatha import DhatuKosha, strip_anubandhas
k = DhatuKosha()
curated = [e for e in k.entries if e["curated"]]
agree = sum(1 for e in curated if strip_anubandhas(e["dhatu_slp1"]) == e["core_root"])
print(f"agreement with curated ground truth: {agree}/{len(curated)} = {agree/len(curated):.1%}")
real = [e for e in k.entries if e["dhatu_slp1"] != "-"]
changed = sum(1 for e in real if not e["curated"])
print(f"real roots: {len(real)}  ('-' placeholders: {len(k.entries) - len(real)})")
EOF
```

**These numbers were measured while writing this plan — they are the expected result, not a guess:**

| measure | before | after |
|---|---|---|
| agreement with the 294 curated roots | 228 (77.6%) | **231 (78.6%)** |
| real roots collapsing to a bare consonant | 7 | **0** |
| roots whose clean form changes | — | 36 |

**If agreement drops below 77.6%, stop** — a fix that reduces agreement with the hand-curated table is wrong; re-check which cluster caused it.

Two things that legitimately remain imperfect after this fix, so they don't surprise you: `Guzi~r` cleans to `Guzi~` (a trailing `~r` residue this function has never handled) and `YizvidA~` cleans to `zvid` rather than `svid`. Both are cleaned up downstream by `DhatuResolver._RESIDUAL` and `_normalize_citation` in Task 3. Do not try to fix them here.

- [ ] **Step 7: Commit**

```bash
git add sanskrit_analyzer/dhatu/dhatupatha.py tests/test_dhatu/test_dhatupatha.py
git commit -m "fix(dhatu): correct it-marker stripping for ghu-/nyi-/ovit roots

Gu was stripped as a cutu marker, destroying 11 roots that own that
initial (ghuna, ghurna, ghusa). Yi (14 roots) and the leading ovit o~
(12 roots) were not stripped at all, so no-hA was left as o~hA and the
downstream residue rule then reduced it to 'o' — making it impossible
to reach, which is why hanam resolved to han 'to kill' rather than
ha 'to abandon'."
```

---

### Task 3: Port the resolver into the analyzer

**Files:**
- Create: `sanskrit_analyzer/dhatu/resolver.py`
- Test: `tests/test_dhatu/test_resolver.py`
- Test: `tests/test_dhatu/test_golden_terms.py`

**Interfaces:**
- Consumes: `strip_anubandhas`, `DhatuKosha` from Tasks 1–2; `resolve_data_dir()` from `sanskrit_analyzer.prakriya.analyzer`.
- Produces:
  - `class DhatuResolver` with `resolve(self, *candidates_slp1: str, preferred_root: str | None = None) -> dict[str, Any] | None`, `is_rootless(self, *candidates_slp1: str) -> bool`, `describe_root(self, root_slp1: str) -> dict[str, Any] | None`.
  - `get_dhatu_resolver() -> DhatuResolver` — process-wide singleton.
  - The returned dict has keys `root_slp1: str`, `prefixes_slp1: list[str]`, `gana: int | None`, `artha_slp1: str | None`, `verified: bool`, `is_verb: bool`.

- [ ] **Step 1: Copy the source file**

```bash
cp ~/Projects/yoga_sutras/backend/app/services/dhatu_resolver.py \
   ~/Projects/sanskrit_analyzer/sanskrit_analyzer/dhatu/resolver.py
```

- [ ] **Step 2: Rewrite the module's imports and drop the sys.path hack**

In `sanskrit_analyzer/dhatu/resolver.py`, replace the entire `_ensure` method and the `__init__` that carries `_slm_path`. The sibling-checkout hack disappears; the Dhātupāṭha is now a sibling module.

```python
    def __init__(self) -> None:
        self._kosha: Any = None
        self._dhatu_kosha: DhatuKosha | None = None
        self._ready: bool | None = None

    def _ensure(self) -> bool:
        """Load the vidyut Kośa and the Dhātupāṭha index once; cache success."""
        if self._ready is not None:
            return self._ready
        try:
            from vidyut.kosha import Kosha

            from sanskrit_analyzer.prakriya.analyzer import resolve_data_dir

            data_dir = resolve_data_dir()
            if data_dir is None:
                raise RuntimeError("vidyut data bundle not found")
            self._kosha = Kosha(os.path.join(str(data_dir), "kosha"))
            self._dhatu_kosha = DhatuKosha()
            self._ready = True
        except Exception as e:  # missing data bundle
            logger.info("DhatuResolver unavailable: %s", e)
            self._ready = False
        return self._ready
```

Add at the top of the file, replacing the old imports:

```python
from __future__ import annotations

import logging
import os
import re
from typing import Any

from sanskrit_analyzer.dhatu.dhatupatha import DhatuKosha, strip_anubandhas

logger = logging.getLogger(__name__)
```

Then replace every `self._strip(...)` call with `strip_anubandhas(...)` and delete the `self._strip` attribute. Update the module docstring to drop all references to `sanskrit_model` and the sibling checkout.

- [ ] **Step 3: Annotate for mypy**

Every method needs annotations. The ported file already annotates most; add `-> None` to `__init__`, and give `_clean_root` its return type:

```python
    def _clean_root(self, aupadeshika: str) -> tuple[str, bool, bool]:
```

Run `mypy sanskrit_analyzer/dhatu/resolver.py` and fix what it reports. Expect complaints about the untyped `_pack` staticmethod — annotate it:

```python
    @staticmethod
    def _pack(
        root_slp1: str,
        prefixes_slp1: list[str],
        gana: int | None,
        artha_slp1: str | None,
        verified: bool,
        is_verb: bool = False,
    ) -> dict[str, Any]:
```

- [ ] **Step 4: Move the tests across**

```bash
cd ~/Projects/sanskrit_analyzer
cp ~/Projects/yoga_sutras/backend/tests/test_dhatu_resolver.py tests/test_dhatu/test_resolver.py
cp ~/Projects/yoga_sutras/backend/tests/test_dhatu_golden_terms.py tests/test_dhatu/test_golden_terms.py
```

In both files, change the import from

```python
from app.services.dhatu_resolver import get_dhatu_resolver
```

to

```python
from sanskrit_analyzer.dhatu.resolver import get_dhatu_resolver
```

and update the skip message in `test_golden_terms.py` from `"vidyut Kośa / sanskrit_model unavailable"` to `"vidyut Kośa unavailable"`.

`test_resolver.py` contains a `TestImplausibleRoots` class whose `test_single_consonant_never_verifies` asserts `strip_anubandhas("GuRa~")` produces something unverifiable. **Task 2 fixed that at source**, so `GuRa~` now cleans to `GuR` and *does* verify. Replace that one test with:

```python
    def test_ghu_root_now_resolves_properly(self, resolver):
        """Task 2 fixed this at source: √ghuṇ keeps its initial and verifies."""
        root, verified, _ = resolver._clean_root("GuRa~")
        assert root == "GuR"
        assert verified is True
```

Keep `test_implausible_root_is_never_reported` — the plausibility guard stays as defence in depth against any future upstream damage.

- [ ] **Step 5: Run the tests**

Run: `cd ~/Projects/sanskrit_analyzer && python -m pytest tests/test_dhatu/ -v`
Expected: PASS. The golden suite should report 29/31 with 2 xfail — the same numbers yoga_sutras had, since nothing about ranking changed.

If the golden suite scores *lower* than 29/31, the port lost something — most likely a `self._strip` call that was not converted, or `DhatuKosha()` failing to find the CSVs. Do not proceed until it matches.

- [ ] **Step 6: Export from the package**

In `sanskrit_analyzer/dhatu/__init__.py`, add:

```python
from sanskrit_analyzer.dhatu.dhatupatha import DhatuKosha, strip_anubandhas
from sanskrit_analyzer.dhatu.resolver import DhatuResolver, get_dhatu_resolver
```

and extend `__all__`:

```python
__all__ = [
    "DhatuIdentifier",
    "DhatuKosha",
    "DhatuResolver",
    "TokenResult",
    "get_dhatu_resolver",
    "rank_analyses",
    "segment",
    "strip_anubandhas",
]
```

- [ ] **Step 7: Commit**

```bash
git add sanskrit_analyzer/dhatu/resolver.py sanskrit_analyzer/dhatu/__init__.py tests/test_dhatu/
git commit -m "feat(dhatu): add DhatuResolver with ranking and upasarga peeling"
```

---

### Task 4: Wire DhatuIdentifier to the resolver

This is where the analyzer's own users (`deep_read/facade.py:222`) get the improvement.

**Files:**
- Modify: `sanskrit_analyzer/dhatu/identifier.py`
- Test: `tests/test_dhatu/test_identifier.py`

**Interfaces:**
- Consumes: `get_dhatu_resolver()` and the resolver result dict from Task 3.
- Produces: `DhatuIdentifier.__init__` gains a third parameter `preferred_root_fn: Callable[[str], str | None] | None = None`. `TokenResult.dhatu` keeps its existing shape, so `deep_read/facade.py` needs no change.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_dhatu/test_identifier.py`. That file already imports `pytest`, `DhatuIdentifier` and `kosha_engine` at the top — add only the resolver import to the existing import block, then append the tests:

```python
from sanskrit_analyzer.dhatu.resolver import get_dhatu_resolver


def _needs_kosha():
    if not get_dhatu_resolver()._ensure():
        pytest.skip("vidyut Kośa unavailable")


def test_identify_gives_clean_roots_not_anubandha_residue():
    """yoga is from √yuj, not from a form still carrying its it-markers."""
    _needs_kosha()
    results = DhatuIdentifier().identify("योगः")
    roots = [r.dhatu["root"] for r in results if r.dhatu]
    assert "yuj" in roots
    assert "yoji" not in roots


def test_identify_peels_upasarga():
    """anuśāsana is anu + √śās; the Kosha files it as an unlinked stem."""
    _needs_kosha()
    results = DhatuIdentifier().identify("अनुशासनम्")
    assert any(r.dhatu and r.dhatu["root"] == "SAs" for r in results)


def test_identify_prefers_ha_over_han_for_hanam():
    """hānam is 'abandonment' (√hā), not 'killing' (√han)."""
    _needs_kosha()
    results = DhatuIdentifier().identify("हानम्")
    roots = [r.dhatu["root"] for r in results if r.dhatu]
    assert "hA" in roots
    assert roots[0] != "han"


def test_preferred_root_hook_settles_a_homograph():
    """A consumer's dictionary outranks every internal heuristic."""
    _needs_kosha()
    ident = DhatuIdentifier(preferred_root_fn=lambda w: "raYj")
    results = ident.identify("रागः")
    assert any(r.dhatu and r.dhatu["root"] == "raYj" for r in results)
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python -m pytest tests/test_dhatu/test_identifier.py -v -k "clean_roots or peels or ha_over_han or preferred_root"`
Expected: FAIL — `test_identify_gives_clean_roots_not_anubandha_residue` asserts `"yuj" in roots` but gets `["yoji"]`; `test_preferred_root_hook_settles_a_homograph` fails with `TypeError: unexpected keyword argument 'preferred_root_fn'`.

- [ ] **Step 3: Add the hook and delegate to the resolver**

In `sanskrit_analyzer/dhatu/identifier.py`, extend `__init__`:

```python
    def __init__(
        self,
        segment_fn: Callable[[str], list[str] | None] | None = None,
        pos_hint_fn: Callable[[str], str | None] | None = None,
        preferred_root_fn: Callable[[str], str | None] | None = None,
    ) -> None:
        self._segment = segment_fn or segmenter.segment
        self._pos_hint = pos_hint_fn
        self._preferred_root = preferred_root_fn
```

Then in `identify`, after `ranked = rank_analyses(...)`, overwrite each analysis's root with the resolver's reading:

```python
            resolver = get_dhatu_resolver()
            slp1 = analysis.get("slp1")
            if slp1 and resolver._ensure():
                preferred = self._preferred_root(member_iast) if self._preferred_root else None
                lemma = next(
                    (a.get("lemma") for a in ranked if a.get("lemma")), slp1
                )
                info = resolver.resolve(slp1, lemma, preferred_root=preferred)
                if info:
                    for a in ranked:
                        if a.get("dhatu"):
                            a["dhatu"]["root"] = info["root_slp1"]
                            a["dhatu"]["root_dev"] = kosha_engine.to_devanagari(
                                info["root_slp1"]
                            )
                            a["dhatu"]["gana_num"] = info["gana"]
                            a["dhatu"]["artha_sa"] = info["artha_slp1"]
                            a["dhatu"]["prefixes"] = info["prefixes_slp1"]
                            a["dhatu"]["verified"] = info["verified"]
                            break
                    else:
                        ranked.insert(0, {
                            "kind": "derived",
                            "lemma": lemma,
                            "dhatu": {
                                "root": info["root_slp1"],
                                "root_dev": kosha_engine.to_devanagari(info["root_slp1"]),
                                "gana_num": info["gana"],
                                "artha_sa": info["artha_slp1"],
                                "prefixes": info["prefixes_slp1"],
                                "verified": info["verified"],
                            },
                            "morphology": {},
                        })
```

Add the import at the top: `from sanskrit_analyzer.dhatu.resolver import get_dhatu_resolver`.

The `for ... else` matters: when the Kośa produced no dhātu-bearing analysis at all (the anuśāsana case, filed as a plain nominal), the resolver's peeled reading is inserted as a new front-ranked analysis. Without the `else` branch, `test_identify_peels_upasarga` stays red.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python -m pytest tests/test_dhatu/ -v`
Expected: PASS. The pre-existing `rank_analyses` tests must still pass — they operate on synthetic dicts and never touch the resolver.

- [ ] **Step 5: Re-measure the golden set through the identifier**

```bash
cd ~/Projects/sanskrit_analyzer && python - <<'EOF'
import re
from sanskrit_analyzer.deep_read import kosha_engine as ke
from sanskrit_analyzer.dhatu import DhatuIdentifier
src = open("tests/test_dhatu/test_golden_terms.py").read()
pairs = [(a, b) for a, b in re.findall(r'\("([A-Za-z~\\\']+)",\s*"([A-Za-z~\\\']+)"\)', src) if len(a) > 1]
ident = DhatuIdentifier()
ok = 0
for slp, exp in pairs:
    res = ident.identify(ke.to_devanagari(slp))
    got = next((r.dhatu["root"] for r in res if r.dhatu), None)
    ok += got == exp
print(f"DhatuIdentifier on golden set: {ok}/{len(pairs)} = {ok/len(pairs):.0%}  (was 32%)")
EOF
```
Expected: substantially above 32%. Record the figure in the commit message. If it is still near 32%, the delegation in Step 3 is not firing — check that `resolver._ensure()` returns True and that `analysis["slp1"]` is populated.

- [ ] **Step 6: Commit**

```bash
git add sanskrit_analyzer/dhatu/identifier.py tests/test_dhatu/test_identifier.py
git commit -m "feat(dhatu): resolve roots through DhatuResolver, add preferred_root hook"
```

---

### Task 5: Point sanskrit_model at the analyzer

**Files:**
- Modify: `~/Projects/sanskrit_model/slm/rules.py:528-640`
- Modify: `~/Projects/sanskrit_model/pyproject.toml`
- Delete: `~/Projects/sanskrit_model/dhatus-full.csv`, `~/Projects/sanskrit_model/dhatus-core.csv`

**Interfaces:**
- Consumes: `strip_anubandhas`, `DhatuKosha` from `sanskrit_analyzer.dhatu.dhatupatha`.
- Produces: `slm.rules.strip_anubandhas` and `slm.rules.DhatuKosha` continue to exist with identical signatures, so all five existing call sites keep working untouched: `evals/eval.py:168,190`, `slm/datagen.py:45,49,246`, `slm/infer.py:35,109`, `demo.py:48,69`.

> ⚠️ **This task changes model training data.** `slm/datagen.py:49` builds training examples from `strip_anubandhas`, and `evals/eval.py` uses `DhatuKosha` as its verification oracle. Task 2 changed the clean root for 37 roots, so generated data and eval baselines shift. The recorded ByT5 root-identification baseline (F1 0.848) was measured with the old behaviour and is no longer comparable. Step 5 re-measures it.

- [ ] **Step 1: Add the dependency**

In `~/Projects/sanskrit_model/pyproject.toml`, extend `dependencies`:

```toml
dependencies = [
    "torch>=2.2",
    "numpy>=1.26",
    "indic-transliteration>=2.3.82",
    "sanskrit-analyzer @ git+https://github.com/naren-m/sanskrit_analyser.git@main",
]
```

For local development, install the analyzer as editable so the changes from Tasks 1–4 are visible before they are pushed:

```bash
cd ~/Projects/sanskrit_model
pip install -e ~/Projects/sanskrit_analyzer
```

- [ ] **Step 2: Write the failing test**

Create `~/Projects/sanskrit_model/tests/test_rules_dhatu_reexport.py`:

```python
"""The Dhatupatha rules now live in sanskrit_analyzer; slm.rules re-exports
them so existing call sites (datagen, infer, evals, demo) keep working."""

from slm import rules


def test_strip_anubandhas_is_the_analyzer_implementation():
    from sanskrit_analyzer.dhatu.dhatupatha import strip_anubandhas

    assert rules.strip_anubandhas is strip_anubandhas


def test_dhatu_kosha_is_the_analyzer_implementation():
    from sanskrit_analyzer.dhatu.dhatupatha import DhatuKosha

    assert rules.DhatuKosha is DhatuKosha


def test_kosha_loads_without_local_csvs():
    """The CSVs are gone from this repo; the index must still build."""
    assert len(rules.DhatuKosha().entries) == 2259


def test_upstream_fixes_are_visible_here():
    assert rules.strip_anubandhas("o~hA\\k") == "hA"
    assert rules.strip_anubandhas("GuRa~") == "GuR"
```

- [ ] **Step 3: Run it to verify it fails**

Run: `cd ~/Projects/sanskrit_model && python -m pytest tests/test_rules_dhatu_reexport.py -v`
Expected: FAIL on `test_strip_anubandhas_is_the_analyzer_implementation` — `rules.strip_anubandhas` is still the local copy, so the identity check fails.

- [ ] **Step 4: Replace the local implementation with a re-export**

In `~/Projects/sanskrit_model/slm/rules.py`, delete lines 528–640 (the `# 3. Dhatu lookup` section: `_IT_PREFIX_CLUSTERS`, `strip_anubandhas`, and `DhatuKosha`) and put in their place:

```python
# ---------------------------------------------------------------------------
# 3. Dhatu lookup  (owned by sanskrit_analyzer)
# ---------------------------------------------------------------------------
#
# The Dhatupatha index and the it-marker stripping moved to
# sanskrit_analyzer.dhatu.dhatupatha, which is now the single owner of that
# data — three projects were carrying partial copies. Re-exported here so
# every existing `rules.DhatuKosha()` / `rules.strip_anubandhas()` call site
# in datagen, infer, evals and demo keeps working unchanged.

from sanskrit_analyzer.dhatu.dhatupatha import (  # noqa: E402
    DhatuKosha,
    strip_anubandhas,
)

__all__ = [*globals().get("__all__", []), "DhatuKosha", "strip_anubandhas"]
```

Then delete the CSVs:

```bash
cd ~/Projects/sanskrit_model && git rm dhatus-full.csv dhatus-core.csv
```

- [ ] **Step 5: Run the model's full test suite and re-measure the eval**

```bash
cd ~/Projects/sanskrit_model
python -m pytest tests/ -v
python evals/eval.py 2>&1 | tail -20
```
Expected: tests PASS. The eval will report **different numbers than the 0.848 baseline** — that is expected and is the point. Record the new figure. If the eval *drops materially*, stop and investigate before committing: the 37 changed roots should help or be neutral, not hurt.

- [ ] **Step 6: Commit**

```bash
cd ~/Projects/sanskrit_model
git add -A
git commit -m "refactor: source Dhatupatha rules from sanskrit_analyzer

The index and it-marker stripping now have one owner. Re-exported from
slm.rules so datagen/infer/evals/demo call sites are unchanged. Note the
upstream fix changes core_root for 37 roots, so training data and eval
baselines shift; new eval figure recorded in the PR."
```

---

### Task 6: Cut yoga_sutras over to the shared resolver

**Files:**
- Delete: `~/Projects/yoga_sutras/backend/app/services/dhatu_resolver.py`
- Delete: `~/Projects/yoga_sutras/backend/tests/test_dhatu_resolver.py`
- Delete: `~/Projects/yoga_sutras/backend/tests/test_dhatu_golden_terms.py`
- Modify: `~/Projects/yoga_sutras/backend/app/services/sanskrit_adapter.py:15` and `:240`

**Interfaces:**
- Consumes: `get_dhatu_resolver()` from `sanskrit_analyzer.dhatu`.
- Produces: no change to `_attach_dhatu`'s output contract — the same `dhatu`, `dhatu_slp1`, `dhatu_devanagari`, `dhatu_meaning`, `dhatu_meaning_en`, `dhatu_prefixes`, `dhatu_verified`, `gana` keys on each word entry.

- [ ] **Step 1: Record the current corpus state as the comparison baseline**

```bash
cd ~/Projects/yoga_sutras
cp data/word_analysis.json /tmp/word_analysis.pre-migration.json
backend/venv/bin/python - <<'EOF'
import json, collections
d = json.load(open("/tmp/word_analysis.pre-migration.json"))
w = [x for b in d.values() for x in b["words"]]
inc = collections.defaultdict(set)
for x in w:
    if x.get("lemma"):
        inc[x["lemma"]].add(x.get("dhatu"))
print(f"words={len(w)} with_dhatu={sum(1 for x in w if x.get('dhatu'))} "
      f"inconsistent_lemmas={sum(1 for v in inc.values() if len(v) > 1)}")
EOF
```
Expected at time of writing: `words=1228 with_dhatu=768 inconsistent_lemmas=10`. These are the numbers Step 6 must match or beat.

- [ ] **Step 2: Point the adapter at the analyzer**

In `backend/app/services/sanskrit_adapter.py`, change line 15 from

```python
from app.services.dhatu_resolver import get_dhatu_resolver
```

to

```python
from sanskrit_analyzer.dhatu import get_dhatu_resolver
```

Nothing else in `_attach_dhatu` changes — it already calls `resolver.is_rootless(...)` and `resolver.resolve(..., preferred_root=cited)`, and both signatures are preserved by Task 3. The MW etymology stays exactly where it is, in this app, feeding in through `preferred_root`.

- [ ] **Step 3: Delete the local copies**

```bash
cd ~/Projects/yoga_sutras
git rm backend/app/services/dhatu_resolver.py \
       backend/tests/test_dhatu_resolver.py \
       backend/tests/test_dhatu_golden_terms.py
```

- [ ] **Step 4: Verify nothing else referenced them**

```bash
cd ~/Projects/yoga_sutras
grep -rn "dhatu_resolver\|sanskrit_model\|slm.rules" backend scripts --include='*.py'
```
Expected: **no output.** Any hit is a straggler that must be repointed before continuing.

- [ ] **Step 5: Run the app's test suite**

Run: `cd ~/Projects/yoga_sutras/backend && ./venv/bin/python -m pytest tests/ -q`
Expected: PASS. The count drops by the tests that moved upstream (the resolver and golden-term suites); everything in `test_sanskrit_adapter.py` and `test_dictionary_service.py` must still pass, including `test_merge_suffix_*`, `test_nominal_resolves_from_its_lemma_not_its_inflection`, and `test_finite_verb_still_resolves_from_its_surface`.

- [ ] **Step 6: Re-run enrichment and compare the corpus**

```bash
cd ~/Projects/yoga_sutras
pgrep -f enrich_word_analysis && echo "STOP: a run is already in flight" || \
  backend/venv/bin/python scripts/enrich_word_analysis.py --byt5
```

> The enrichment writes to SQLite before it writes the JSON cache. If a second copy is running, or a dev server holds a write transaction, it dies with `database is locked` and writes **no cache at all** — leaving the old file in place, which looks like success. Always check `pgrep` first, and confirm the cache's mtime actually changed afterwards. A full run is ~20–30 minutes and only prints progress every 20 blocks, so early silence is normal.

Then compare:

```bash
cd ~/Projects/yoga_sutras && backend/venv/bin/python - <<'EOF'
import json, collections
def stats(p):
    d = json.load(open(p))
    w = [x for b in d.values() for x in b["words"]]
    inc = collections.defaultdict(set)
    for x in w:
        if x.get("lemma"):
            inc[x["lemma"]].add(x.get("dhatu"))
    return len(w), sum(1 for x in w if x.get("dhatu")), sum(1 for v in inc.values() if len(v) > 1)
for name, p in (("before", "/tmp/word_analysis.pre-migration.json"),
                ("after", "data/word_analysis.json")):
    t, dh, ic = stats(p)
    print(f"{name:8} words={t} with_dhatu={dh} ({dh/t:.1%}) inconsistent={ic}")
EOF
```
Expected: `with_dhatu` equal or higher, `inconsistent` equal or lower. Task 2's fix should also recover √ghuṇ-family roots if any appear in the corpus. **If coverage drops, do not commit** — diff the two JSONs per word to find which lemmas lost roots and why.

- [ ] **Step 7: Commit**

```bash
cd ~/Projects/yoga_sutras
git add -A
git commit -m "refactor: use the shared dhatu resolver from sanskrit_analyzer

Deletes the app's local resolver and the sys.path hack that reached into
a sibling sanskrit_model checkout — an undeclared dependency that silently
yielded no roots wherever that directory was absent. The MW etymology
stays here and feeds in via preferred_root."
```

---

## Rollback

Each task is a single commit in one repo, so `git revert` per repo is sufficient. The ordering constraint is that **Task 5 and Task 6 depend on Tasks 1–4 being published**. Until the analyzer changes are pushed to `main`, both consumers must install it editable (`pip install -e ~/Projects/sanskrit_analyzer`); a rollback of the analyzer alone would break them.

Safest revert order is the reverse of the plan: yoga_sutras (Task 6) → sanskrit_model (Task 5) → analyzer (Tasks 4→1). Tasks 1–4 are additive and safe to leave in place even if 5 and 6 are reverted, since nothing outside the analyzer imports them until then.

The one irreversible-by-revert artifact is `data/word_analysis.json`, which Task 6 Step 6 regenerates. `/tmp/word_analysis.pre-migration.json` from Step 1 is the restore point; copy it back and re-seed if needed.

## Out of scope

- `sanskrit_analyzer/data/comprehensive_dhatu_database.db` and `data/dhatu_db.py` — a separate lower-coverage lookup, left untouched.
- The `abhāva → √bhā` misranking (a noun with a spurious finite-verb homograph). The `pos_hint_fn` the analyzer already has is the natural fix, but wiring POS-hint ranking into `DhatuResolver._best_candidate` is its own piece of work with its own evaluation.
- `ramayanam`, which will inherit the improvement on its next analyzer bump but needs no changes here.
- The MW/Apte dictionaries stay in `yoga_sutras`. A previous investigation concluded they are project-specific; the `preferred_root_fn` hook is what makes that separation work.
