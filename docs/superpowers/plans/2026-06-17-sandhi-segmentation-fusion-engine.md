# Sandhi/Segmentation Fusion Engine — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `sanskrit_analyzer.Analyzer` actually return vidyut's word-level segmentation with dhatus (it currently collapses to the unsplit line), add a kosha cross-check that fixes cheda's mis-splits, measure it against a hand-labeled Rāmāyaṇa gold set, and make the Ramayanam Deep Read POC a thin client of the upstream engine.

**Architecture:** vidyut-cheda already segments + tags (works). The bug is `SplitValidator`, whose 99-word vocabulary scores real lemmas as unknown and lets a "simplicity bonus" collapse the correct split back to one segment. We (1) back the validator's vocabulary with `vidyut.kosha`, (2) add a kosha-validated de-sandhi fallback for tokens cheda leaves unanalyzed and a guard against splitting tokens that are themselves valid kosha lemmas (fixes `niyatātmā`→`niyatAt+mA`), (3) build a gold-verse eval harness, (4) repoint Ramayanam Deep Read at `Analyzer`.

**Tech Stack:** Python 3.11, `vidyut` 0.4.0 (`cheda`, `kosha`, `lipi`), pytest, FastAPI/Flask (ramayanam).

**Repos:** Tasks 1–4 in `~/Projects/sanskrit_analyzer`. Task 5 in `~/Projects/ramayanam`. Branch each repo (e.g. `feat/segmentation-fusion`) — never commit to main.

**Empirical anchors (verified 2026-06-17):**
- `VidyutEngine().analyze("स गच्छति वनम्")` → 4 Segments incl. `gacCati` lemma `gam` `tinanta.si.thi.lat`. Engine WORKS.
- `Analyzer().analyze("स गच्छति वनम्")` → unsplit line. Stub is `SplitValidator`.
- `Chedaka("<root vidyut-data dir>")` loads (pass ROOT, not `cheda/` subdir); mis-splits `niyatātmā`→`niyatAt+mA`, `mahāvīryo`→`mahO+Iryas`.
- Kosha keyed in SLP1; needs de-sandhi (`-o`→`-as/-a`, `-H`→`-s/-r`).

---

### Task 1: Kosha-backed vocabulary so the validator keeps correct splits

**Files:**
- Create: `sanskrit_analyzer/validation/kosha_vocabulary.py`
- Modify: `sanskrit_analyzer/analyzer.py:156-160` (build validator with kosha vocab)
- Test: `tests/validation/test_kosha_vocabulary.py`, `tests/test_analyzer_segmentation.py`

- [ ] **Step 1: Read the interface the validator depends on.** Open `sanskrit_analyzer/validation/vocabulary.py` and note the exact methods `SplitValidator` calls: `contains(lemma)`, `is_indeclinable(text)`, `find_stem(surface)`. The new class must implement the same three (duck-typed).

- [ ] **Step 2: Write the failing test** (`tests/validation/test_kosha_vocabulary.py`):

```python
import pytest
from sanskrit_analyzer.validation.kosha_vocabulary import KoshaVocabulary

@pytest.fixture(scope="module")
def vocab():
    return KoshaVocabulary()  # resolves vidyut data dir internally

def test_contains_known_lemma(vocab):
    assert vocab.contains("gam")        # √gam is in the kosha
    assert vocab.contains("vana")
    assert not vocab.contains("xyzzqq")

def test_find_stem_for_inflected_form(vocab):
    # an inflected form's stem is discoverable
    assert vocab.find_stem("gacCati") is not None

def test_indeclinable_passthrough(vocab):
    # falls back to the curated indeclinable set; must not crash
    assert isinstance(vocab.is_indeclinable("ca"), bool)
```

- [ ] **Step 3: Run it — expect failure** (`ImportError`): `cd ~/Projects/sanskrit_analyzer && .venv/bin/python -m pytest tests/validation/test_kosha_vocabulary.py -q`. Expected: FAIL (module missing).

- [ ] **Step 4: Implement `KoshaVocabulary`.** It wraps `vidyut.kosha.Kosha` and delegates indeclinables to the existing curated `Vocabulary`. `contains`/`find_stem` query the kosha with the de-sandhi candidates.

```python
"""Vocabulary backed by the full vidyut kosha (millions of forms).

The curated Vocabulary only had ~99 entries, which made SplitValidator score
real lemmas as unknown and collapse correct splits. This delegates membership
to the kosha and keeps the curated indeclinable list.
"""
from __future__ import annotations
import functools
from sanskrit_analyzer.validation.vocabulary import Vocabulary
from sanskrit_analyzer.engines.vidyut_engine import DEFAULT_VIDYUT_DATA_PATH


def _desandhi(slp: str) -> list[str]:
    out = [slp]
    if slp:
        stem, last = slp[:-1], slp[-1]
        if last == "H": out += [stem + "s", stem + "r"]
        elif last == "o": out += [stem + "as", stem + "aH", stem + "a"]
        elif last in ("S", "z"): out += [stem + "H", stem + "s"]
        elif last == "M": out += [stem + "m"]
    seen, uniq = set(), []
    for c in out:
        if c and c not in seen:
            seen.add(c); uniq.append(c)
    return uniq


class KoshaVocabulary:
    def __init__(self, data_path: str | None = None) -> None:
        from vidyut.kosha import Kosha
        import os
        root = data_path or DEFAULT_VIDYUT_DATA_PATH
        self._kosha = Kosha(os.path.join(root, "kosha"))
        self._curated = Vocabulary.load_default() if hasattr(Vocabulary, "load_default") else Vocabulary()

    @functools.lru_cache(maxsize=20000)
    def _has(self, form: str) -> bool:
        try:
            return any(len(self._kosha.get(c)) > 0 for c in _desandhi(form))
        except Exception:
            return False

    def contains(self, lemma: str) -> bool:
        return bool(lemma) and self._has(lemma)

    def find_stem(self, surface: str):
        return surface if self.contains(surface) else None

    def is_indeclinable(self, text: str) -> bool:
        return self._curated.is_indeclinable(text)
```

> NOTE: confirm `Vocabulary`'s constructor/loader name in Step 1 and adjust the `_curated` line accordingly.

- [ ] **Step 5: Run the vocab test — expect PASS.** Same command as Step 3.

- [ ] **Step 6: Wire it into the Analyzer.** In `analyzer.py` around line 156-160, build the validator with the kosha vocab, falling back to the curated one on failure:

```python
# Initialize split validator with kosha-backed vocabulary
try:
    from sanskrit_analyzer.validation.kosha_vocabulary import KoshaVocabulary
    vocab = KoshaVocabulary()
except Exception as exc:
    logger.warning("KoshaVocabulary unavailable (%s); using curated vocab", exc)
    vocab = Vocabulary()
self._split_validator = SplitValidator(vocab)
logger.info("Split validator using %s", type(vocab).__name__)
```

- [ ] **Step 7: Write the black-box segmentation test** (`tests/test_analyzer_segmentation.py`):

```python
import asyncio
import pytest
from sanskrit_analyzer import Analyzer, AnalysisMode

@pytest.fixture(scope="module")
def az():
    return Analyzer()

def _words(tree):
    return [w for p in tree.parse_forest[:1] for sg in p.sandhi_groups for w in sg.base_words]

def test_simple_sentence_is_segmented(az):
    tree = asyncio.run(az.analyze("स गच्छति वनम्", mode=AnalysisMode.EDUCATIONAL))
    words = _words(tree)
    assert len(words) >= 3, f"expected >=3 words, got {[w.surface_form for w in words]}"

def test_verb_carries_dhatu(az):
    tree = asyncio.run(az.analyze("स गच्छति वनम्", mode=AnalysisMode.EDUCATIONAL))
    roots = {w.dhatu.dhatu for w in _words(tree) if getattr(w, "dhatu", None)}
    assert "gam" in roots
```

- [ ] **Step 8: Run it — expect PASS now** (was the core stub): `.venv/bin/python -m pytest tests/test_analyzer_segmentation.py -q`. If `len(words)` is still 1, the simplicity bonus is still winning — proceed to Task 1b.

- [ ] **Step 9 (Task 1b, only if Step 8 still collapses): cap the simplicity bonus / never merge across whitespace.** In `split_validator.py:_generate_candidates`, do not emit the single whole-string candidate when `original_slp1` contains a space; and in `score_candidate` clamp `simplicity_bonus` to `min(simplicity_bonus, 1.0)`. Re-run Step 8.

- [ ] **Step 10: Commit.**

```bash
git add sanskrit_analyzer/validation/kosha_vocabulary.py sanskrit_analyzer/analyzer.py tests/
git commit -m "fix(analyzer): back split-validator with kosha vocab so segmentation survives"
```

---

### Task 2: Don't split a token that is itself a valid kosha lemma (fix cheda mis-splits)

**Problem:** cheda mis-splits lexicalized compounds — `niyatātmā`→`niyatAt`+`mA`, `mahāvīryo`→`mahO`+`Iryas`. But `niyatAtmA`/`mahAvIrya` ARE single kosha entries.

**Files:** Modify `sanskrit_analyzer/validation/split_validator.py` (`_generate_candidates` + `score_candidate`). Test: `tests/validation/test_no_oversplit.py`.

- [ ] **Step 1: Failing test** — the whole-token analysis must win when it validates in kosha:

```python
import asyncio
from sanskrit_analyzer import Analyzer, AnalysisMode

def _surfaces(tree):
    return [w.surface_form for p in tree.parse_forest[:1]
            for sg in p.sandhi_groups for w in sg.base_words]

def test_niyatatma_not_oversplit():
    az = Analyzer()
    tree = asyncio.run(az.analyze("नियतात्मा", mode=AnalysisMode.EDUCATIONAL))
    s = _surfaces(tree)
    assert s == ["niyatAtmA"] or "niyatAtmA" in s, f"over-split: {s}"
```

- [ ] **Step 2: Run — expect FAIL** (cheda over-splits). Command: `.venv/bin/python -m pytest tests/validation/test_no_oversplit.py -q`.

- [ ] **Step 3: Implement the guard.** In `_generate_candidates`, always add the **whole-token-as-one** candidate, and in `score_candidate` add a strong bonus when the single whole token is a valid kosha lemma:

```python
# in _generate_candidates, after adding the original split:
_add([Segment(surface=original_slp1, lemma=original_slp1, pos=None)])

# in score_candidate, inside the per-seg loop, replace the contains() branch:
elif self._vocab.contains(seg.surface):     # whole inflected form is a known pada
    score += 2.5
```

- [ ] **Step 4: Run — expect PASS.** Re-run Step 2 command. Also re-run Task 1's tests (no regression).

- [ ] **Step 5: Commit.** `git commit -am "fix(validator): prefer whole-token analysis when it is a valid kosha pada"`

---

### Task 3: De-sandhi fallback for tokens cheda leaves unanalyzed

**Problem:** True compounds (`ikzvAkuvaMSapraBavo`) and glued pairs come back from cheda as one token with `data=None`. Provide a kosha-validated fallback and an honest "compound" tag rather than empty output.

**Files:** Modify `sanskrit_analyzer/engines/vidyut_engine.py` (post-process `Chedaka.run` tokens). Test: `tests/engines/test_vidyut_fallback.py`.

- [ ] **Step 1: Failing test:**

```python
from sanskrit_analyzer.engines.vidyut_engine import VidyutEngine

def test_unanalyzed_token_gets_desandhi_or_compound_flag():
    e = VidyutEngine()
    res = e.analyze("इक्ष्वाकुवंशप्रभवो रामो नाम")
    by_surface = {s.surface: s for s in res.segments}
    # रामो must resolve to a real lemma after de-sandhi
    assert any(s.lemma for s in res.segments if s.surface.startswith("rAm"))
```

- [ ] **Step 2: Run — expect FAIL** (rAmo may currently lack lemma). Command: `.venv/bin/python -m pytest tests/engines/test_vidyut_fallback.py -q`.

- [ ] **Step 3: Implement.** Where `vidyut_engine` maps `Chedaka` tokens → `Segment`, for any token whose `data is None`, run a kosha lookup over `_desandhi(token.text)` (reuse the helper from `kosha_vocabulary`); on a hit, fill `lemma`/`pos`/dhatu from the first `PadaEntry`; on miss, set `pos="compound"` when `len(text) >= 11`.

- [ ] **Step 4: Run — expect PASS.** Re-run Step 2 command.

- [ ] **Step 5: Commit.** `git commit -am "feat(vidyut): kosha de-sandhi fallback for tokens cheda leaves unanalyzed"`

---

### Task 4: Rāmāyaṇa gold-verse evaluation harness

**Files:** Create `tests/eval/ramayana_gold.jsonl` (hand-labeled), `tests/eval/segmentation_eval.py`. Test: `tests/eval/test_gold_regression.py`.

- [ ] **Step 1: Hand-label ~15 padas.** Each line: the surface pada (Devanagari), expected SLP1 segmentation (list), and expected roots where applicable. Seed with the user's verse (1.1.8). Example lines:

```jsonl
{"verse":"1.1.8","surface":"रामो","expect_words":["rAma"],"expect_roots":[]}
{"verse":"1.1.8","surface":"गच्छति","expect_words":["gam"],"expect_roots":["gam"]}
{"verse":"1.1.8","surface":"नियतात्मा","expect_words":["niyatAtmA"],"expect_roots":[]}
{"verse":"1.1.8","surface":"इक्ष्वाकुवंशप्रभवो","expect_words":["ikzvAku","vaMSa","praBava"],"expect_roots":[]}
```

- [ ] **Step 2: Write the eval runner** (`segmentation_eval.py`): load the jsonl, run each `surface` through `Analyzer`, compare predicted lemmas/roots to expected; print per-item pass/fail + aggregate word-accuracy and root-accuracy.

- [ ] **Step 3: Write a regression test** that asserts aggregate root-accuracy ≥ a floor (start at the measured baseline, e.g. `>= 0.5`) so future changes can't silently regress:

```python
from tests.eval.segmentation_eval import run_eval
def test_gold_root_accuracy_floor():
    report = run_eval()
    assert report["root_accuracy"] >= 0.5, report
```

- [ ] **Step 4: Run, record the real baseline, set the floor to it.** Command: `.venv/bin/python -m pytest tests/eval/test_gold_regression.py -q`.

- [ ] **Step 5: Commit.** `git commit -am "test(eval): Rāmāyaṇa gold-verse segmentation regression harness"`

---

### Task 5: Repoint Ramayanam Deep Read at the upstream Analyzer (thin client)

**Files (in `~/Projects/ramayanam`):** Modify `api/services/deep_read/deep_read_service.py` to call `sanskrit_analyzer.Analyzer` and map `AnalysisTree`→deep-read JSON; keep `vidyut_engine.py` as a fallback. Test: `tests/unit/test_deep_read_engine.py`.

- [ ] **Step 1: Failing test** — the user's verse resolves the simple padas via the upstream Analyzer:

```python
from api.services.deep_read import deep_read_service as svc
def test_running_text_verse_segments():
    out = svc.analyze_text("इक्ष्वाकुवंशप्रभवो रामो नाम जनैश्श्रुतः नियतात्मा महावीर्यो द्युतिमान्धृतिमान् वशी")
    resolved = [t for t in out["tokens"] if t["resolved"]]
    assert len(resolved) >= 6
```

- [ ] **Step 2: Run — expect FAIL** (current kosha-only path resolves ~5/8). Command: `cd ~/Projects/ramayanam && .venv/bin/python -m pytest tests/unit/test_deep_read_engine.py::test_running_text_verse_segments -q`.

- [ ] **Step 3: Implement the mapping.** Add `analyze_via_analyzer(text)` that calls `Analyzer().analyze(text, mode=EDUCATIONAL)`, iterates `best_parse.sandhi_groups[*].base_words[*]`, and emits the existing token/analysis dict shape (reuse `_classify`/`_dhatu_view` field names). Use it in `analyze_text`, falling back to the local kosha engine if the import/analyzer fails.

- [ ] **Step 4: Run — expect PASS.** Re-run Step 2. Then full suite: `.venv/bin/python -m pytest tests/unit/test_deep_read_engine.py -q`.

- [ ] **Step 5: Manual verify.** Restart server, open `/deep-read`, paste verse 1.1.8, confirm ≥6 padas show roots and compounds are labelled. 

- [ ] **Step 6: Commit (ramayanam).** `git commit -am "feat(deep-read): consume sanskrit_analyzer Analyzer as segmentation engine"`

---

## Notes / Decisions
- Eval = hand-labeled Rāmāyaṇa gold set (user choice). Keep it small but real; grow as failures surface.
- Disambiguation beyond the kosha-validity guard (Task 2) is deferred until the gold harness shows where it's needed.
- Ambuda.org is the reference UX for the eventual word-by-word reader.
