# Integration Completion & Engine Improvements Design

**Date:** 2026-03-31
**Status:** Approved
**Depends on:** [2026-03-17 Sanskrit Analyzer Integration Design](2026-03-17-sanskrit-analyzer-integration-design.md)

## Overview

Complete the partially-finished integration of `sanskrit_analyzer` into `ramayanam` and `yoga_sutras`, then improve the analysis engines for production-quality accuracy and confidence scoring.

## Goals

1. **Finish integration** — All Sanskrit NLP in both consuming projects flows through `SanskritAdapter`
2. **Fix engine foundations** — Heritage engine functional, confidence calibrated, ensemble weights normalized
3. **Enhance capabilities** — Full morphological tag decoding, sandhi/prakriya extraction, performance tuning

## Current State

### Sanskrit Analyzer (this repo)
- 515 tests, 4 engines (Vidyut, Dharmamitra, Heritage, LocalByT5), MCP server, API, UI
- `lookup_dhatu()` and `dictionary_lookup()` public API merged (PR #1)
- LocalByT5 engine added for offline neural analysis

### Ramayanam Integration (~40% complete)
- Done: SanskritAdapter created, requirements.txt updated, morphology_controller rewired, old services deleted
- Remaining: dhatu_controller, dictionary_controller, guru_service, broken tests

### Yoga Sutras Integration (~70% complete)
- Done: SanskritAdapter created, requirements.txt updated, split/morphology routes rewired, dharmamitra_service + sandhi_service deleted
- Remaining: dictionary_service.py still used, vidyut-data/ (77MB) not deleted, no tests

### Engine Issues
- Heritage engine HTML parsing is stubbed (non-functional)
- All engines use hardcoded confidence values
- Ensemble weights sum to 1.45 (not normalized after LocalByT5 addition)
- Morphology/POS not voted on in ensemble (only lemmas)

---

## Phase A: Finish Integration

### A1: Ramayanam (feature/sanskrit-analyzer-integration branch)

**A1.1: Rewire dhatu_controller.py**
- Currently uses direct SQLite queries against `comprehensive_dhatu_database.db`
- Replace with `SanskritAdapter.lookup_dhatu()` calls
- Affected endpoints: `/api/dhatu/search`, `/api/dhatu/all`, `/api/dhatu/<id>`

**A1.2: Dictionary controller decision**
- `dictionary_controller.py` uses `DictionaryService` which has its own multi-source dictionary implementation
- Decision: **Keep DictionaryService as-is** — it provides project-specific dictionary features (multi-source lookup, formatting) that go beyond what `sanskrit_analyzer.dictionary_lookup()` offers
- No rewiring needed; document this decision

**A1.3: Update guru_service.py**
- Currently makes minimal Sanskrit-related calls
- Update to use `SanskritAdapter.analyze_sloka()` for entity extraction where it processes Sanskrit text
- Low priority — only update if it currently calls deleted services

**A1.4: Fix broken tests**
- `tests/unit/test_dharmamitra_service.py` imports deleted `api.services.dharmamitra_service`
- Delete this test file
- Create `tests/unit/test_sanskrit_adapter.py` testing the new adapter
- Verify remaining test suite passes

### A2: Yoga Sutras (feature/sanskrit-analyzer-integration branch)

**A2.1: Replace dictionary_service.py**
- Route `/api/dictionary/<word>` still uses `DictionaryService.get_definitions()`
- Rewire to `SanskritAdapter.dictionary_lookup()`
- Delete `backend/app/services/dictionary_service.py`

**A2.2: Delete vidyut-data/**
- 77MB directory at `data/vidyut-data/` no longer needed
- Sanskrit analyzer bundles its own data

**A2.3: Add tests**
- Create `backend/tests/test_sanskrit_adapter.py`
- Test SanskritAdapter methods (split_sandhi, analyze_word, dictionary_lookup)
- Test route integration with mocked adapter

### A3: Phase 5 Cleanup (all repos)

**A3.1: Update READMEs**
- Document sanskrit_analyzer dependency in both projects
- Remove references to Vidyut/Dharmamitra direct usage

**A3.2: Update Docker files**
- Remove vidyut-data volume mounts from yoga_sutras docker-compose
- Ensure sanskrit_analyzer installs correctly in Docker builds

**A3.3: Update CI/CD**
- Ensure git dependency resolves in CI (may need SSH key or token for private repo)
- Update Jenkinsfiles if they reference old services

### A4: Validation
- All 515 tests pass in sanskrit_analyzer
- Ramayanam tests pass on integration branch
- Yoga Sutras tests pass on integration branch
- Manual E2E: word clicks, dictionary panels, dhatu lookup work in both projects

---

## Phase B: Fix Engine Foundations

### B1: Heritage Engine — Real HTML Parsing

**Problem:** HTML parsing at `heritage_engine.py:84-141` is stubbed. Returns original text as single segment with hardcoded confidence.

**Solution:**
- Implement proper HTML parsing using regex or BeautifulSoup
- Extract lemmas, morphological tags, POS from Heritage's HTML output structure
- Parse case, gender, number from Heritage's morphological descriptions
- Return actual segments with real confidence (based on parse success)
- If Heritage is unreachable or returns unparseable HTML, return empty result with confidence=0

**Alternative:** If Heritage's HTML format is too unstable to parse reliably, disable Heritage from the default ensemble config and reduce to a 3-engine system (Vidyut + Dharmamitra + LocalByT5). This is acceptable — the original spec noted Heritage as weight=0.25 (lowest).

### B2: Normalize Ensemble Weights

**Problem:** Weights sum to 1.45 after LocalByT5 (0.45) was added to existing Vidyut (0.35) + Dharmamitra (0.40) + Heritage (0.25).

**Solution:**
- Normalize weights at ensemble initialization time (divide each by sum)
- Store both raw and normalized weights
- Default weights for 4-engine config: Vidyut=0.24, Dharmamitra=0.28, Heritage=0.17, LocalByT5=0.31
- Default weights for 3-engine config (no Heritage): Vidyut=0.29, Dharmamitra=0.33, LocalByT5=0.38
- Make weights configurable via Config

### B3: Confidence Calibration

**Problem:** All engines return hardcoded confidence (Vidyut=0.9, Dharmamitra=0.92, Heritage=0.5-0.7, LocalByT5=0.90).

**Solution per engine:**

| Engine | Confidence Source |
|--------|------------------|
| Vidyut | Number of valid parses found vs ambiguity level. Single unambiguous parse = high, multiple = lower |
| Dharmamitra | API returns confidence scores if available; otherwise based on completeness of morphological tags returned |
| Heritage | Based on successful HTML parse vs fallback |
| LocalByT5 | Extract beam search scores from model output (sequence probability) |

- Confidence should range 0.0-1.0 and reflect actual parse quality
- Add a `_compute_confidence()` method to each engine

### B4: Morphology and POS Voting in Ensemble

**Problem:** Only lemmas get majority voting. Morphology and POS use the first engine's value arbitrarily.

**Solution:**
- Implement majority voting for POS (same logic as lemma voting)
- For morphology: merge tags from all engines, prefer the most detailed tag set
- When engines disagree on POS, record the disagreement in the segment's metadata
- Weight votes by engine confidence (not just engine weight)

---

## Phase C: Enhance Capabilities

### C1: Complete LocalByT5 Tag Decoding

**Problem:** Tags like "SNM" only extract POS from first character, discarding case/gender/number.

**Solution:**
- Investigate the ByT5-Sanskrit compact tag format (reference: Nehrdich et al. 2024) and build a decoder mapping each position to its morphological category
- Populate full `MorphologicalTag` from decoded values
- Enables proper morphology voting in ensemble

### C2: Extract Sandhi Info from Vidyut

**Problem:** Vidyut provides sandhi rule information in `raw_output` but it's not extracted into `Segment.sandhi_info`.

**Solution:**
- Parse Vidyut's prakriya/rule data from raw_output
- Populate `SandhiInfo` with rule type and Ashtadhyayi sutra reference where available
- Populate `Segment.prakriya` with derivation steps

### C3: Performance Tuning

**Problem:** Heritage Engine has 10-second timeout; no per-engine latency targets.

**Solution:**
- Set per-engine timeouts: Vidyut/LocalByT5 < 2s, Dharmamitra < 5s, Heritage < 5s
- Add timeout configuration to Config
- If an engine times out, proceed with available results (don't block ensemble)
- Add per-engine latency logging for monitoring

### C4: Integration Tests

**Problem:** All engine tests use mocks. No tests with real engine data.

**Solution:**
- Add test fixtures with known-correct Sanskrit analysis results
- Create integration tests that verify engine output format (not requiring live engines)
- Add benchmark tests comparing engine outputs for a standard test set
- Mark integration tests with `@pytest.mark.integration` so they can be skipped in CI

---

## Implementation Sequence

```
Phase A (Integration)          Phase B (Engines)           Phase C (Enhance)
├─ A1: Ramayanam rewiring     ├─ B1: Heritage parsing     ├─ C1: Tag decoding
├─ A2: Yoga Sutras cleanup    ├─ B2: Weight normalization ├─ C2: Sandhi extraction
├─ A3: Cleanup & docs         ├─ B3: Confidence scoring   ├─ C3: Performance tuning
└─ A4: Validation             └─ B4: Morph/POS voting     └─ C4: Integration tests
```

Phase A is independent of B and C. Phases B and C are in this repo only.

Within Phase B: B2 (weights) should come before B4 (voting) since voting uses weights. B1 (Heritage) and B3 (confidence) are independent.

Within Phase C: C1 (tag decoding) should come before C4 (integration tests) since tests validate decoded output.

## Success Criteria

- [ ] Ramayanam: all controllers use SanskritAdapter or documented exception
- [ ] Ramayanam: tests pass on integration branch
- [ ] Yoga Sutras: no old service files remain, vidyut-data deleted
- [ ] Yoga Sutras: tests pass on integration branch
- [ ] Heritage engine returns real parsed segments (or is disabled with documented reason)
- [ ] Ensemble weights normalize to 1.0
- [ ] Each engine computes confidence from actual parse quality
- [ ] Ensemble votes on morphology and POS, not just lemmas
- [ ] LocalByT5 fully decodes morphological tags
- [ ] All 515+ tests pass in sanskrit_analyzer
- [ ] E2E: word clicks, dictionary panels, dhatu lookup work in both consuming projects

## File Change Summary

| Location | Files Added | Files Modified | Files Deleted |
|----------|-------------|----------------|---------------|
| ramayanam | 1 (test_sanskrit_adapter.py) | 2-3 (dhatu_controller, guru_service) | 1 (test_dharmamitra_service.py) |
| yoga_sutras | 1 (test_sanskrit_adapter.py) | 1 (dictionary_routes.py) | 2 (dictionary_service.py, data/vidyut-data/) |
| sanskrit_analyzer/engines | 0 | 5 (heritage, ensemble, vidyut, dharmamitra, local_byt5) | 0 |
| sanskrit_analyzer/tests | 1-2 (integration tests) | 3-5 (engine tests updated) | 0 |
