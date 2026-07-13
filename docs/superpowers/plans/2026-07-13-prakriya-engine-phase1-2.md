# Prakriyā Engine (Phase 1+2) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Single-pada Sanskrit analyzer with full Pāṇinian rule tracing (analysis-by-synthesis via vidyut) plus chandas (meter) identification — Phases 1–2 of `docs/prakriya-engine-design.md`.

**Architecture:** New package `sanskrit_analyzer/prakriya/`. For each input word: normalize to SLP1 → look up analyses in `vidyut.kosha` → re-generate each analysis forward through `vidyut.prakriya.Vyakarana.derive()` → keep only analyses whose generated surface form matches → the derivation `history` (list of `Step`s with sūtra codes) joined against `Data.load_sutras()` + `kashika.tsv` is the displayed proof. Meter ID wraps `vidyut.chandas` with a hand-coded anuṣṭubh (pathyā/vipulā) fallback, since śloka is not a fixed L/G template.

**Tech Stack:** Python 3.10+, vidyut 0.4.0 (already a dependency), pytest, existing `sanskrit_analyzer.utils` transliteration.

## Global Constraints

- Data bundle: resolved via existing `sanskrit_analyzer.deep_read.kosha_engine.resolve_data_dir()` (checks `VIDYUT_DATA_DIR`, `<cwd>/vidyut-0.4.0`, `~/.vidyut-data`). Never hardcode `~/.vidyut-data`.
- All internal text is SLP1. Reuse `sanskrit_analyzer.utils.normalize.detect_script` and `sanskrit_analyzer.utils.transliterate.to_slp1` — do not write new transliteration code.
- Every vidyut-dependent test must `pytest.importorskip("vidyut")` AND skip when `resolve_data_dir()` returns None (pattern: module-level `pytestmark`).
- Verified analyses only: an analysis whose forward generation does not reproduce the surface form is dropped, never shown. If nothing verifies, return empty list — never fabricate (design doc §6 ārṣa-prayoga).
- `kashika.tsv` in the bundle is a 10-row stub — gloss is `None` when absent; code must not assume coverage.
- Full suite `uv run pytest` must pass before commit (Dharmamitra-dependent tests auto-skip).
- Run `code-simplifier:code-simplifier` agent after all tasks (project CLAUDE.md mandate).

## Deferred (later plans)

Phases 3–5: sandhi-split lattice (`rules.csv` inversion), DCS disambiguation LM, kṛdanta/taddhita/samāsa recursion, uṇādi fallback, PyCDSL/Amarakośa semantics, FastAPI/web UI, Kaumudī re-ordering, jāti/mātrā meters.

---

### Task 1: Sūtra index (`sutra_index.py`)

**Files:**
- Create: `sanskrit_analyzer/prakriya/__init__.py`
- Create: `sanskrit_analyzer/prakriya/sutra_index.py`
- Test: `tests/prakriya/__init__.py`, `tests/prakriya/test_sutra_index.py`

**Interfaces:**
- Consumes: `vidyut.prakriya.Data`, `resolve_data_dir()` from deep_read.
- Produces: `Sutra` dataclass `(code: str, source: str, text: str, kashika: str | None)`; `SutraIndex.load(data_dir: Path | None = None) -> SutraIndex`; `SutraIndex.lookup(code: str) -> Sutra | None`; module-level `get_index() -> SutraIndex` (cached).

- [ ] **Step 1: Write the failing test**

```python
# tests/prakriya/test_sutra_index.py
"""Tests for the sūtra code -> text/gloss index."""
import pytest

vidyut = pytest.importorskip("vidyut")

from sanskrit_analyzer.deep_read.kosha_engine import resolve_data_dir

pytestmark = pytest.mark.skipif(
    resolve_data_dir() is None, reason="vidyut data bundle not installed"
)

from sanskrit_analyzer.prakriya.sutra_index import SutraIndex, get_index


def test_lookup_known_sutra():
    idx = SutraIndex.load()
    s = idx.lookup("1.3.1")
    assert s is not None
    assert s.code == "1.3.1"
    assert "BUvAdayo" in s.text


def test_lookup_unknown_code_returns_none():
    idx = SutraIndex.load()
    assert idx.lookup("99.99.99") is None


def test_kashika_stub_tolerated():
    # Bundle kashika.tsv has ~9 rows; 3.2.93 is one of them.
    idx = SutraIndex.load()
    s = idx.lookup("3.2.93")
    assert s is not None and s.kashika  # covered row has gloss
    s2 = idx.lookup("1.3.1")
    assert s2 is not None  # uncovered row: kashika is None, no crash
    assert s2.kashika is None


def test_get_index_cached():
    assert get_index() is get_index()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/prakriya/test_sutra_index.py -v`
Expected: FAIL/ERROR with `ModuleNotFoundError: No module named 'sanskrit_analyzer.prakriya'`

- [ ] **Step 3: Write minimal implementation**

```python
# sanskrit_analyzer/prakriya/__init__.py
"""Prakriyā engine: verse-to-dhātu analysis with Pāṇinian rule tracing.

Phase 1+2 of docs/prakriya-engine-design.md: normalization, chandas
identification, and single-pada analysis-by-synthesis over vidyut.
"""
```

```python
# sanskrit_analyzer/prakriya/sutra_index.py
"""Sūtra code -> (text, Kāśikā gloss) lookup for prakriyā trace display.

Sūtra texts come from ``vidyut.prakriya.Data.load_sutras()`` (Aṣṭādhyāyī,
vārttikas, Dhātupāṭha etc. — 5k+ rows keyed by code). The Kāśikā gloss joins
from the bundle's ``prakriya/kashika.tsv``, which is currently a small stub —
coverage is sparse by design, so ``kashika`` is Optional.
"""
from __future__ import annotations

import csv
import logging
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from sanskrit_analyzer.deep_read.kosha_engine import VidyutUnavailable, resolve_data_dir

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Sutra:
    code: str          # e.g. "3.4.78"
    source: str        # e.g. "ashtadhyayi", "dhatupatha"
    text: str          # sūtra text in SLP1
    kashika: str | None = None


class SutraIndex:
    def __init__(self, sutras: dict[str, Sutra]):
        self._sutras = sutras

    @classmethod
    def load(cls, data_dir: Path | None = None) -> "SutraIndex":
        data_dir = data_dir or resolve_data_dir()
        if data_dir is None:
            raise VidyutUnavailable(
                "vidyut data bundle not found; cannot build sūtra index."
            )
        from vidyut.prakriya import Data

        kashika = _load_kashika(data_dir / "prakriya" / "kashika.tsv")
        sutras: dict[str, Sutra] = {}
        for s in Data(str(data_dir / "prakriya")).load_sutras():
            # Later sources may repeat a code; first (Aṣṭādhyāyī) wins.
            sutras.setdefault(
                s.code,
                Sutra(
                    code=s.code,
                    source=str(s.source),
                    text=s.text,
                    kashika=kashika.get(s.code),
                ),
            )
        return cls(sutras)

    def lookup(self, code: str) -> Sutra | None:
        return self._sutras.get(code)

    def __len__(self) -> int:
        return len(self._sutras)


def _load_kashika(path: Path) -> dict[str, str]:
    """Parse kashika.tsv (columns: code, text). Missing/short file is fine."""
    if not path.is_file():
        return {}
    out: dict[str, str] = {}
    with path.open(encoding="utf-8") as fh:
        for row in csv.DictReader(fh, delimiter="\t"):
            code, text = row.get("code"), row.get("text")
            if code and text:
                out[code] = text
    return out


@lru_cache(maxsize=1)
def get_index() -> SutraIndex:
    return SutraIndex.load()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/prakriya/test_sutra_index.py -v`
Expected: 4 PASS

- [ ] **Step 5: Commit**

```bash
git add sanskrit_analyzer/prakriya/ tests/prakriya/
git commit -m "feat(prakriya): sūtra index joining vidyut sutrapatha with kashika gloss"
```

---

### Task 2: Input normalization (`normalize.py`)

**Files:**
- Create: `sanskrit_analyzer/prakriya/normalize.py`
- Test: `tests/prakriya/test_normalize.py`

**Interfaces:**
- Consumes: `detect_script` (`sanskrit_analyzer.utils.normalize`), `to_slp1` (`sanskrit_analyzer.utils.transliterate`), `Script` enum.
- Produces: `NormalizedInput` dataclass `(raw: str, script: str, slp1: str, words: list[str])`; `normalize(text: str) -> NormalizedInput`. `words` = whitespace-split SLP1 tokens with daṇḍas/digits stripped, avagraha (`'`) preserved.

- [ ] **Step 1: Write the failing test**

```python
# tests/prakriya/test_normalize.py
"""Input normalization: any script -> clean SLP1 word list."""
from sanskrit_analyzer.prakriya.normalize import normalize


def test_devanagari_to_slp1():
    n = normalize("भवति")
    assert n.script == "devanagari"
    assert n.slp1 == "Bavati"
    assert n.words == ["Bavati"]


def test_iast_verse_with_dandas_and_verse_number():
    n = normalize("dharmakṣetre kurukṣetre māmakāḥ pāṇḍavāś ca । १.१ ॥")
    assert n.words[0] == "Darmakzetre"
    assert "॥" not in n.slp1 and "।" not in n.slp1
    assert not any(w.strip(".|0123456789") == "" for w in n.words)


def test_avagraha_preserved():
    # avagraha is sandhi evidence (rAmo 'sti) — must survive normalization
    n = normalize("रामो ऽस्ति")
    assert n.words == ["rAmo", "'sti"]


def test_empty_input():
    n = normalize("   ")
    assert n.words == [] and n.slp1 == ""
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/prakriya/test_normalize.py -v`
Expected: FAIL with `ModuleNotFoundError` (normalize module absent)

- [ ] **Step 3: Write minimal implementation**

```python
# sanskrit_analyzer/prakriya/normalize.py
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


@dataclass(frozen=True)
class NormalizedInput:
    raw: str
    script: str
    slp1: str
    words: list[str]


def normalize(text: str) -> NormalizedInput:
    raw = text or ""
    stripped = raw.strip()
    if not stripped:
        return NormalizedInput(raw=raw, script="unknown", slp1="", words=[])
    script = detect_script(stripped)
    slp1 = to_slp1(stripped, script) if script != Script.SLP1 else stripped
    slp1 = _WS.sub(" ", _STRIP.sub(" ", slp1)).strip()
    # SLP1 uses '.' for daṇḍa in some sources; drop bare punctuation tokens.
    words = [w for w in slp1.split() if w.strip(".'-") or w == "'"]
    words = [w.strip(".") for w in words if w.strip(".")]
    return NormalizedInput(raw=raw, script=script.value, slp1=slp1, words=words)
```

Note: check `Script.value` exists (`sanskrit_analyzer/models/scripts.py`); if the enum uses `.name`, adapt (`script.value` vs `script.name.lower()`), keeping the test's `"devanagari"` expectation.

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/prakriya/test_normalize.py -v`
Expected: 4 PASS

- [ ] **Step 5: Commit**

```bash
git add sanskrit_analyzer/prakriya/normalize.py tests/prakriya/test_normalize.py
git commit -m "feat(prakriya): input normalization to SLP1 word list"
```

---

### Task 3: Chandas identifier (`chandas.py`)

**Files:**
- Create: `sanskrit_analyzer/prakriya/chandas.py`
- Test: `tests/prakriya/test_chandas.py`

**Interfaces:**
- Consumes: `vidyut.chandas.Chandas` (constructor takes `<data_dir>/chandas/meters.tsv` path; `classify(slp1) -> Match` with `.padya` (meter name or None) and `.aksharas` (list of rows of `Akshara(text, weight)` where weight is `"G"`/`"L"`)), `resolve_data_dir()`.
- Produces: `ChandasResult` dataclass `(name: str | None, scans: list[str], notes: str | None)` where `scans` is one `"GGLG..."` string per pāda row; `identify(slp1_verse: str) -> ChandasResult`; pure helper `anushtubh_form(scans: list[str]) -> str | None` returning `"paTyA"` / `"vipulA"` / `None`.

- [ ] **Step 1: Write the failing test**

```python
# tests/prakriya/test_chandas.py
"""Meter identification: vidyut vṛtta matching + hand-coded anuṣṭubh rules."""
import pytest

vidyut = pytest.importorskip("vidyut")

from sanskrit_analyzer.deep_read.kosha_engine import resolve_data_dir

pytestmark = pytest.mark.skipif(
    resolve_data_dir() is None, reason="vidyut data bundle not installed"
)

from sanskrit_analyzer.prakriya.chandas import anushtubh_form, identify


def test_mandakranta_identified():
    # Meghadūta 1.1 first pāda pair
    r = identify("kaScitkAntAvirahaguruRA svADikArapramattaH")
    assert r.name == "mandAkrAntA"
    assert r.scans and all(ch in "GL" for ch in r.scans[0])


def test_anushtubh_pathya_fallback():
    # BG 2.47: karmaṇy evādhikāras te... vidyut returns no vṛtta; our rule fires.
    r = identify("karmaRyevADikAraste mA Palezu kadAcana . "
                 "mA karmaPalaheturBUrmA te saNgo 'stvakarmaRi")
    assert r.name is not None and "anuzwuB" in r.name


def test_anushtubh_form_pure_function():
    # pathyā: 8 syll/pāda, 5th L, 6th G, 7th G in odd pādas / L in even pādas
    odd, even = "GGGGLGGG", "GGGGLGLG"
    assert anushtubh_form([odd, even, odd, even]) == "paTyA"
    assert anushtubh_form(["GGGG", "GG", "G", "G"]) is None  # not 8-syllable


def test_prose_returns_none_name():
    r = identify("rAmaH gacCati")
    assert r.name is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/prakriya/test_chandas.py -v`
Expected: FAIL with `ModuleNotFoundError` (chandas module absent)

- [ ] **Step 3: Write minimal implementation**

```python
# sanskrit_analyzer/prakriya/chandas.py
"""Chandas (meter) identification.

``vidyut.chandas`` handles fixed-template vṛttas via meters.tsv. The śloka
(anuṣṭubh) is NOT a fixed L/G template, so when vidyut finds no match we apply
the classical pathyā/vipulā checks ourselves (design doc §3.3.5):

* every pāda has 8 syllables;
* syllables 2–3 are never both laghu;
* syllable 5 is laghu and 6 is guru (pāda-final syllable is anceps);
* syllable 7: guru in odd pādas -> pathyā; other odd-pāda shapes -> vipulā.
  Even pādas always need 7th laghu (ja-gaṇa at 5–7).
"""
from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache

from sanskrit_analyzer.deep_read.kosha_engine import VidyutUnavailable, resolve_data_dir


@dataclass(frozen=True)
class ChandasResult:
    name: str | None        # e.g. "mandAkrAntA", "anuzwuB (paTyA)"
    scans: list[str]        # per-pāda weight strings, e.g. "GGLG..."
    notes: str | None = None


@lru_cache(maxsize=1)
def _classifier():
    data_dir = resolve_data_dir()
    if data_dir is None:
        raise VidyutUnavailable("vidyut data bundle not found; chandas unavailable.")
    from vidyut.chandas import Chandas

    return Chandas(str(data_dir / "chandas" / "meters.tsv"))


def identify(slp1_verse: str) -> ChandasResult:
    match = _classifier().classify(slp1_verse.replace(".", " "))
    scans = [
        "".join(str(a.weight) for a in row) for row in (match.aksharas or [])
    ]
    if match.padya is not None:
        return ChandasResult(name=str(match.padya), scans=scans)
    form = anushtubh_form(_as_four_padas(scans))
    if form:
        return ChandasResult(name=f"anuzwuB ({form})", scans=scans)
    return ChandasResult(
        name=None, scans=scans, notes="no meter matched (prose or corrupt text?)"
    )


def _as_four_padas(scans: list[str]) -> list[str]:
    """vidyut may scan a śloka as 2 half-verse rows of 16; split to 4×8."""
    if len(scans) == 2 and all(len(s) == 16 for s in scans):
        return [scans[0][:8], scans[0][8:], scans[1][:8], scans[1][8:]]
    return scans


def anushtubh_form(scans: list[str]) -> str | None:
    """Return "paTyA"/"vipulA" if the 4 pāda scans satisfy śloka rules, else None."""
    if len(scans) != 4 or any(len(s) != 8 for s in scans):
        return None
    for s in scans:
        if s[1] == "L" and s[2] == "L":  # syllables 2–3 both laghu: forbidden
            return None
    # even pādas (2nd, 4th): 5–7 must be ja-gaṇa (L G L)
    for s in (scans[1], scans[3]):
        if s[4:7] != "LGL":
            return None
    # odd pādas: 5=L, 6=G required; 7=G -> pathyā, else vipulā
    for s in (scans[0], scans[2]):
        if s[4] != "L" or s[5] != "G":
            return "vipulA"  # vipulā variants relax 5–7; be permissive but labeled
    if all(s[6] == "G" for s in (scans[0], scans[2])):
        return "paTyA"
    return "vipulA"


def is_available() -> bool:
    return resolve_data_dir() is not None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/prakriya/test_chandas.py -v`
Expected: 4 PASS. If `test_anushtubh_pathya_fallback` fails because vidyut scans the BG line into a different row shape, print `identify(...).scans` and adjust `_as_four_padas` (the pure-function test pins the rule logic; the adapter may need the actual row shape).

- [ ] **Step 5: Commit**

```bash
git add sanskrit_analyzer/prakriya/chandas.py tests/prakriya/test_chandas.py
git commit -m "feat(prakriya): chandas identifier with anuṣṭubh pathyā/vipulā fallback"
```

---

### Task 4: Verified pada analyzer with rule trace (`analyzer.py`)

**Files:**
- Create: `sanskrit_analyzer/prakriya/analyzer.py`
- Test: `tests/prakriya/test_analyzer.py`

**Interfaces:**
- Consumes: `vidyut.kosha.Kosha` (`.get(slp1) -> list[PadaEntry]`, each with `.lemma`, `.to_prakriya_args()`), `vidyut.prakriya.Vyakarana().derive(args) -> list[Prakriya]` (`.text`, `.history: list[Step]`, `Step.code/.source/.result`), `SutraIndex.lookup` (Task 1), `desandhi_candidates` from `deep_read.kosha_engine`.
- Produces:
  - `PrakriyaStep` dataclass `(step: int, form: str, code: str, source: str, sutra_text: str | None, kashika: str | None)`
  - `PadaAnalysis` dataclass `(surface: str, lookup_form: str, kind: str, lemma: str, morph: str, verified: bool, prakriya: list[PrakriyaStep])` with `.to_dict()`
  - `analyze_pada(word_slp1: str, limit: int = 5) -> list[PadaAnalysis]` — verified analyses only, deduped by (kind, lemma, morph).

- [ ] **Step 1: Write the failing test**

```python
# tests/prakriya/test_analyzer.py
"""Analysis-by-synthesis: kosha lookup verified by forward generation."""
import pytest

vidyut = pytest.importorskip("vidyut")

from sanskrit_analyzer.deep_read.kosha_engine import resolve_data_dir

pytestmark = pytest.mark.skipif(
    resolve_data_dir() is None, reason="vidyut data bundle not installed"
)

from sanskrit_analyzer.prakriya.analyzer import analyze_pada


def test_bhavati_verified_with_trace():
    analyses = analyze_pada("Bavati")
    assert analyses, "Bavati must yield at least one verified analysis"
    a = analyses[0]
    assert a.verified is True
    assert a.lemma == "BU"
    codes = [s.code for s in a.prakriya]
    assert "3.4.78" in codes       # tiptasJi... (tiN assignment)
    assert "7.3.84" in codes       # sārvadhātukārdhadhātukayoḥ (guṇa)
    guna = next(s for s in a.prakriya if s.code == "7.3.84")
    assert guna.sutra_text and "sArvaDAtuka" in guna.sutra_text
    assert a.prakriya[-1].form == "Bavati"


def test_final_visarga_form_resolves_via_desandhi():
    # kosha keys pausal -H forms as -s; desandhi_candidates bridges that.
    analyses = analyze_pada("rAmaH")
    assert any(a.lemma == "rAma" for a in analyses)


def test_gibberish_returns_empty_never_fabricates():
    assert analyze_pada("xyzzyq") == []


def test_dedup_and_limit():
    analyses = analyze_pada("Bavati", limit=3)
    assert len(analyses) <= 3
    keys = [(a.kind, a.lemma, a.morph) for a in analyses]
    assert len(keys) == len(set(keys))


def test_to_dict_roundtrip():
    a = analyze_pada("gacCati")[0]
    d = a.to_dict()
    assert d["lemma"] == "gam"
    assert d["prakriya"][0]["code"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/prakriya/test_analyzer.py -v`
Expected: FAIL with `ModuleNotFoundError` (analyzer module absent)

- [ ] **Step 3: Write minimal implementation**

```python
# sanskrit_analyzer/prakriya/analyzer.py
"""Single-pada analysis by synthesis (design doc §3.5–3.7).

For each kosha analysis of a word we re-derive the surface form through
vidyut-prakriya. A match proves the analysis, and the derivation history —
sūtra by sūtra — is the displayable proof. Non-matching analyses are dropped;
nothing is ever fabricated.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from functools import lru_cache

from sanskrit_analyzer.deep_read.kosha_engine import (
    VidyutUnavailable,
    desandhi_candidates,
    resolve_data_dir,
)
from sanskrit_analyzer.prakriya.sutra_index import get_index

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class PrakriyaStep:
    step: int
    form: str               # joined result at this step, e.g. "Bo + a + ti"
    code: str               # sūtra code, e.g. "7.3.84"
    source: str             # "ashtadhyayi", "dhatupatha", ...
    sutra_text: str | None
    kashika: str | None

    def to_dict(self) -> dict:
        return {
            "step": self.step, "form": self.form, "code": self.code,
            "source": self.source, "sutra_text": self.sutra_text,
            "kashika": self.kashika,
        }


@dataclass(frozen=True)
class PadaAnalysis:
    surface: str            # word as given (post-normalization SLP1)
    lookup_form: str        # desandhi candidate that hit the kosha
    kind: str               # "Tinanta" / "Subanta" / ...
    lemma: str
    morph: str              # human-readable feature summary from the entry
    verified: bool
    prakriya: list[PrakriyaStep] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "surface": self.surface, "lookup_form": self.lookup_form,
            "kind": self.kind, "lemma": self.lemma, "morph": self.morph,
            "verified": self.verified,
            "prakriya": [s.to_dict() for s in self.prakriya],
        }


@lru_cache(maxsize=1)
def _kosha():
    data_dir = resolve_data_dir()
    if data_dir is None:
        raise VidyutUnavailable("vidyut data bundle not found.")
    from vidyut.kosha import Kosha

    return Kosha(str(data_dir / "kosha"))


@lru_cache(maxsize=1)
def _vyakarana():
    from vidyut.prakriya import Vyakarana

    return Vyakarana()


def _entry_kind(entry) -> str:
    # PyPadaEntry_Tinanta -> "Tinanta"
    return type(entry).__name__.rsplit("_", 1)[-1]


def _trace(prakriya) -> list[PrakriyaStep]:
    idx = get_index()
    steps: list[PrakriyaStep] = []
    for i, s in enumerate(prakriya.history, start=1):
        sutra = idx.lookup(s.code)
        steps.append(
            PrakriyaStep(
                step=i,
                form=" + ".join(str(t) for t in s.result),
                code=s.code,
                source=str(s.source),
                sutra_text=sutra.text if sutra else None,
                kashika=sutra.kashika if sutra else None,
            )
        )
    return steps


def analyze_pada(word_slp1: str, limit: int = 5) -> list[PadaAnalysis]:
    """Return verified analyses (with rule traces) for one SLP1 word."""
    word = (word_slp1 or "").strip().lstrip("'")
    if not word:
        return []
    kosha, vyakarana = _kosha(), _vyakarana()
    out: list[PadaAnalysis] = []
    seen: set[tuple[str, str, str]] = set()
    for candidate in desandhi_candidates(word):
        for entry in kosha.get(candidate):
            kind, lemma, morph = _entry_kind(entry), entry.lemma or "", str(entry)
            key = (kind, lemma, morph)
            if key in seen:
                continue
            try:
                prakriyas = vyakarana.derive(entry.to_prakriya_args())
            except Exception as exc:  # entry types derive() can't take yet
                logger.debug("derive failed for %s (%s): %s", candidate, kind, exc)
                continue
            match = next((p for p in prakriyas if p.text == candidate), None)
            if match is None:
                continue  # analysis did not verify — drop, never fabricate
            seen.add(key)
            out.append(
                PadaAnalysis(
                    surface=word, lookup_form=candidate, kind=kind,
                    lemma=lemma, morph=morph, verified=True,
                    prakriya=_trace(match),
                )
            )
            if len(out) >= limit:
                return out
    return out
```

Note: `morph=str(entry)` is a placeholder-quality summary; if the repr is unhelpfully long, extract from the entry's typed accessors (Tinanta entries expose lakāra/puruṣa/vacana etc. — inspect `dir(entry)` and build `morph` as e.g. `"law kartari praTama eka"`). Keep whatever the tests can pin.

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/prakriya/test_analyzer.py -v`
Expected: 5 PASS. Likely adjustment: `rAmaH` test — confirm which desandhi candidate (`rAmas`/`rAmar`) hits; if neither, check `kosha.get("rAma")` stem behavior and extend `desandhi_candidates` usage accordingly (do not weaken the assertion).

- [ ] **Step 5: Commit**

```bash
git add sanskrit_analyzer/prakriya/analyzer.py tests/prakriya/test_analyzer.py
git commit -m "feat(prakriya): verified pada analyzer with sūtra-cited rule traces"
```

---

### Task 5: Verse facade + JSON schema (`engine.py`)

**Files:**
- Create: `sanskrit_analyzer/prakriya/engine.py`
- Modify: `sanskrit_analyzer/prakriya/__init__.py` (export `analyze_verse`)
- Test: `tests/prakriya/test_engine.py`

**Interfaces:**
- Consumes: `normalize()` (Task 2), `identify()`/`is_available` (Task 3), `analyze_pada()` (Task 4).
- Produces: `analyze_verse(text: str, limit_per_word: int = 5) -> dict` matching design doc §3.9 subset:

```
{"input": {"raw", "script", "slp1"},
 "chandas": {"name", "scans", "notes"} | None,
 "padas": [{"surface", "analyses": [PadaAnalysis.to_dict()...]}]}
```

- [ ] **Step 1: Write the failing test**

```python
# tests/prakriya/test_engine.py
"""End-to-end verse facade: normalize -> chandas -> per-word verified analyses."""
import pytest

vidyut = pytest.importorskip("vidyut")

from sanskrit_analyzer.deep_read.kosha_engine import resolve_data_dir

pytestmark = pytest.mark.skipif(
    resolve_data_dir() is None, reason="vidyut data bundle not installed"
)

from sanskrit_analyzer.prakriya import analyze_verse


def test_devanagari_word_end_to_end():
    rec = analyze_verse("भवति")
    assert rec["input"]["slp1"] == "Bavati"
    assert rec["input"]["script"] == "devanagari"
    assert rec["padas"][0]["surface"] == "Bavati"
    top = rec["padas"][0]["analyses"][0]
    assert top["verified"] and top["lemma"] == "BU"
    assert any(s["code"] == "7.3.84" for s in top["prakriya"])


def test_verse_gets_chandas_block():
    rec = analyze_verse("kaScitkAntAvirahaguruRA svADikArapramattaH")
    assert rec["chandas"]["name"] == "mandAkrAntA"


def test_unanalyzable_word_yields_empty_analyses():
    rec = analyze_verse("xyzzyq")
    assert rec["padas"][0]["analyses"] == []


def test_json_serializable():
    import json

    json.dumps(analyze_verse("गच्छति"))
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/prakriya/test_engine.py -v`
Expected: FAIL with `ImportError: cannot import name 'analyze_verse'`

- [ ] **Step 3: Write minimal implementation**

```python
# sanskrit_analyzer/prakriya/engine.py
"""Verse-level facade: normalize -> chandas -> per-word verified analyses."""
from __future__ import annotations

import logging

from sanskrit_analyzer.prakriya import chandas as chandas_mod
from sanskrit_analyzer.prakriya.analyzer import analyze_pada
from sanskrit_analyzer.prakriya.normalize import normalize

logger = logging.getLogger(__name__)


def analyze_verse(text: str, limit_per_word: int = 5) -> dict:
    n = normalize(text)
    record: dict = {
        "input": {"raw": n.raw, "script": n.script, "slp1": n.slp1},
        "chandas": None,
        "padas": [],
    }
    if n.words and chandas_mod.is_available():
        try:
            c = chandas_mod.identify(n.slp1)
            record["chandas"] = {"name": c.name, "scans": c.scans, "notes": c.notes}
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
```

```python
# sanskrit_analyzer/prakriya/__init__.py  (replace file)
"""Prakriyā engine: verse-to-dhātu analysis with Pāṇinian rule tracing.

Phase 1+2 of docs/prakriya-engine-design.md: normalization, chandas
identification, and single-pada analysis-by-synthesis over vidyut.
"""
from sanskrit_analyzer.prakriya.engine import analyze_verse

__all__ = ["analyze_verse"]
```

Caveat: `engine.py` imports `analyzer.py`, which imports vidyut-dependent modules lazily — check `from sanskrit_analyzer.prakriya import analyze_verse` works without the data bundle (imports must stay cheap/lazy; only *calls* may raise `VidyutUnavailable`).

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/prakriya/test_engine.py -v`
Expected: 4 PASS

- [ ] **Step 5: Commit**

```bash
git add sanskrit_analyzer/prakriya/engine.py sanskrit_analyzer/prakriya/__init__.py tests/prakriya/test_engine.py
git commit -m "feat(prakriya): verse facade with JSON output schema"
```

---

### Task 6: CLI (`__main__.py`)

**Files:**
- Create: `sanskrit_analyzer/prakriya/__main__.py`
- Test: `tests/prakriya/test_cli.py`

**Interfaces:**
- Consumes: `analyze_verse` (Task 5).
- Produces: `uv run python -m sanskrit_analyzer.prakriya "<verse>"` → human-readable trace to stdout; `--json` flag → raw JSON. `main(argv: list[str] | None = None) -> int` for testability.

- [ ] **Step 1: Write the failing test**

```python
# tests/prakriya/test_cli.py
"""CLI smoke tests (capsys, no subprocess)."""
import json

import pytest

vidyut = pytest.importorskip("vidyut")

from sanskrit_analyzer.deep_read.kosha_engine import resolve_data_dir

pytestmark = pytest.mark.skipif(
    resolve_data_dir() is None, reason="vidyut data bundle not installed"
)

from sanskrit_analyzer.prakriya.__main__ import main


def test_json_output(capsys):
    assert main(["--json", "भवति"]) == 0
    rec = json.loads(capsys.readouterr().out)
    assert rec["padas"][0]["analyses"][0]["lemma"] == "BU"


def test_human_output_shows_sutra_codes(capsys):
    assert main(["Bavati"]) == 0
    out = capsys.readouterr().out
    assert "7.3.84" in out and "BU" in out


def test_no_args_is_error(capsys):
    assert main([]) == 2
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/prakriya/test_cli.py -v`
Expected: FAIL with `ModuleNotFoundError` (no `__main__` module)

- [ ] **Step 3: Write minimal implementation**

```python
# sanskrit_analyzer/prakriya/__main__.py
"""CLI: python -m sanskrit_analyzer.prakriya "verse" [--json]"""
from __future__ import annotations

import argparse
import json
import sys

from sanskrit_analyzer.prakriya import analyze_verse


def _render(record: dict) -> str:
    lines: list[str] = []
    ch = record.get("chandas") or {}
    if ch.get("name"):
        lines.append(f"chandas: {ch['name']}")
    for pada in record["padas"]:
        lines.append(f"\n{pada['surface']}")
        if not pada["analyses"]:
            lines.append("  (no Pāṇinian derivation found)")
        for a in pada["analyses"]:
            lines.append(f"  {a['kind']}  lemma={a['lemma']}  [{a['morph']}]")
            for s in a["prakriya"]:
                text = f" — {s['sutra_text']}" if s["sutra_text"] else ""
                lines.append(f"    {s['step']:>2}. {s['form']}  (A. {s['code']}){text}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m sanskrit_analyzer.prakriya",
        description="Analyze a Sanskrit verse down to dhātus with sūtra-cited "
        "derivations.",
    )
    parser.add_argument("verse", nargs="?", help="verse text in any script")
    parser.add_argument("--json", action="store_true", help="emit raw JSON")
    args = parser.parse_args(argv)
    if not args.verse:
        parser.print_usage(sys.stderr)
        return 2
    record = analyze_verse(args.verse)
    print(json.dumps(record, ensure_ascii=False, indent=2) if args.json
          else _render(record))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/prakriya/test_cli.py -v`
Expected: 3 PASS. Also smoke: `uv run python -m sanskrit_analyzer.prakriya "भवति"` shows a numbered trace ending in `Bavati`.

- [ ] **Step 5: Commit**

```bash
git add sanskrit_analyzer/prakriya/__main__.py tests/prakriya/test_cli.py
git commit -m "feat(prakriya): CLI renderer for verse analysis with rule traces"
```

---

### Task 7: Golden verse test + full-suite gate

**Files:**
- Test: `tests/prakriya/test_golden.py`

**Interfaces:**
- Consumes: `analyze_verse` (Task 5). No new production code.

- [ ] **Step 1: Write the golden test**

```python
# tests/prakriya/test_golden.py
"""Golden verse: BG 2.47 pāda a — hand-verified expectations (design doc §5)."""
import pytest

vidyut = pytest.importorskip("vidyut")

from sanskrit_analyzer.deep_read.kosha_engine import resolve_data_dir

pytestmark = pytest.mark.skipif(
    resolve_data_dir() is None, reason="vidyut data bundle not installed"
)

from sanskrit_analyzer.prakriya import analyze_verse

BG_2_47_A = "कर्मण्येवाधिकारस्ते मा फलेषु कदाचन"


def test_bg_2_47_structure():
    rec = analyze_verse(BG_2_47_A)
    surfaces = [p["surface"] for p in rec["padas"]]
    assert "Palezu" in surfaces
    phalesu = next(p for p in rec["padas"] if p["surface"] == "Palezu")
    assert any(
        a["lemma"] == "Pala" and a["verified"] for a in phalesu["analyses"]
    ), "Palezu must verify as saptamī bahuvacana of Pala"


def test_every_verified_analysis_has_cited_trace():
    rec = analyze_verse(BG_2_47_A)
    for pada in rec["padas"]:
        for a in pada["analyses"]:
            assert a["verified"]
            assert a["prakriya"], f"verified analysis of {pada['surface']} lacks trace"
            assert all(s["code"] for s in a["prakriya"])
```

- [ ] **Step 2: Run golden test**

Run: `uv run pytest tests/prakriya/test_golden.py -v`
Expected: 2 PASS (sandhied chunks like `karmaRyevADikAraste` correctly yield empty analyses — Phase 3 territory; the test only pins the unsandhied word).

- [ ] **Step 3: Run the FULL suite**

Run: `uv run pytest`
Expected: all ~755 existing tests + ~24 new ones pass (Dharmamitra-dependent tests auto-skip).

- [ ] **Step 4: Commit**

```bash
git add tests/prakriya/test_golden.py
git commit -m "test(prakriya): golden BG 2.47 verse expectations"
```

---

### Task 8: Simplifier pass + PR

- [ ] **Step 1:** Run `code-simplifier:code-simplifier` agent over `sanskrit_analyzer/prakriya/` (project CLAUDE.md mandate). Apply accepted simplifications; re-run `uv run pytest tests/prakriya/ -v`.
- [ ] **Step 2:** Full suite once more: `uv run pytest` → green.
- [ ] **Step 3:** Commit any simplifier changes: `git commit -am "refactor(prakriya): simplifier pass"`.
- [ ] **Step 4:** Push branch and open PR against `main` titled "feat: prakriyā engine phase 1+2 — chandas + verified pada analyzer with sūtra traces", body summarizing design doc linkage, verified-only discipline, deferred phases.
