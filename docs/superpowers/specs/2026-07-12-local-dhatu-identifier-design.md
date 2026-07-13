# Local Generic Dhātu Identifier — Design Spec

**Date:** 2026-07-12
**Goal:** Remove the remote Dharmamitra API dependency and replace it with a local,
offline, generic dhātu (verbal root) identifier built on Āṣṭādhyāyī-grounded rules,
Vidyut, and a locally-cached ByT5 model.
**Provenance:** Synthesized from a 4-agent research + 2-round debate (Vidyut empirical,
Dharmamitra excision map, Pāṇinian algorithm, local-infra inventory).

---

## 1. Problem framing

The phrase "dhātu identifier" is misleading about where the work is. Empirically:

- **Form → root is already solved locally** by `vidyut.kosha`, a 75 MB prebuilt index
  under `~/.vidyut-data/kosha`. It resolves the full inflectional + derivational space
  offline — every lākāra, plus causative/desiderative/passive/krdanta, plus suppletion.
  Verified live: `gacchati→gam`, `jagāma→gam (liṭ)`, `kṛtvā→kṛ`, `babhūva→bhū`,
  `paśyati→dṛś`, `śrutaḥ→√śru`.
- **The empty sqlite `dhatu_db`** (`comprehensive_dhatu_database.db`) is a scaffold:
  `dhatus` = 20 rows, `dhatu_conjugations` = **0 rows**. It is *not* a reverse index and
  is a dead end for identification. Retained only as an English/Hindi gloss table for
  ~20 common roots.
- **A hand-written reverse-derivation rule engine is the wrong backbone.** Pāṇini's
  grammar is generative; inverting it is under-specified at exactly the hard cases
  (guṇa ambiguity, reduplication, suppletion). Kosha *is* the generate-and-match index —
  reverse-rules would reinvent it. (Agent C retracted its "mandatory suppletion table"
  position after verifying `kosha.get("paśyati") → dṛś` out of the box.)

**The one genuinely unsolved problem is segmentation** — splitting running verse text
with sandhi and samāsa into padas. Kosha keys on pre-sandhi padas and cannot consume
raw verse. Vidyut's *packaged* segmenter (`cheda.Chedaka`) provably fails on real
Rāmāyaṇa compounds:

```
इक्ष्वाकुवंशप्रभवो  → 1 token, data=None       (no analysis)
तपस्स्वाध्यायनिरतं  → []                        (total failure)
niyatAtmA           → niyatAt+mA               (mangles a valid pada)
```

But Vidyut ships the **primitive** to build a working splitter, and a locally-cached
ByT5 model can rerank/tag the results.

---

## 2. Architecture: a tiered segmentation → identification pipeline

A raw Devanagari verse line flows through tiers that degrade gracefully. Each tier is
independently testable.

| Tier | Component | Tech | Role |
|------|-----------|------|------|
| 0 | De-sandhi normalizer | rules (`H→s/r`, `M→m`, `o→as/aḥ`, voiced-final devoicing) | **Load-bearing glue** — applied before every kosha probe. Not optional: without `o→as`, `prabhavo` misses and the whole compound split collapses. |
| 1 | Whitespace tokenize + `kosha.get` per pada | `vidyut.kosha` | Resolves the bulk (~75%) of inflected words directly. |
| 2 | Sandhi-aware DP compound splitter | `vidyut.sandhi.Splitter.from_csv` + kosha as validator | Splits samāsa/sandhi that Tier 1 misses. DP objective = fewest kosha-valid pieces. Sound + complete + polynomial. Raises recall to ~88%. |
| 3 | ByT5 reranker + POS tagger | `chronbmm/sanskrit5-multitask` (cached, greedy decode) | Reranks Tier-2 candidate splits, supplies POS to disambiguate. Closes the last ~10-15% → ~98%. |
| — | Dhātu attribution per segment | `vidyut.kosha` | Each final segment → root + gaṇa + lākara + meaning. |
| — | Candidate ranking | ByT5 POS prior, else demote-short-root-verb rule | Fixes homograph misfires (see §4). |

**Why both rules and ByT5 (the debate resolution):** they are complementary, not
competing. The rules-DP (Agent A) is a fast, deterministic *candidate generator* that
splits `इक्ष्वाकुवंशप्रभवो → [ikṣvāku, vaṃśa, prabhava]` in <1 ms with no model, but
cannot *rank* among multiple valid splits (`munipuṃgavam → mu+nipuṃ+gavam` is a
valid-but-wrong min-piece path). ByT5 (Agent D, greedy decoding) is the learned
*reranker/tagger* that resolves exactly that ambiguity and emits POS that fixes the
ranking bug. v1 ships both (Tier 0-3).

---

## 3. The ByT5 fix (Tier 3 enabler)

The cached `chronbmm/sanskrit5-multitask` (2.2 GB, offline) currently produces garbage
because of the generation config in `engines/local_byt5_engine.py:188-193`. The real
bug is **`early_stopping=True` under `num_beams=4`**, which terminates the beam at the
first EOS and truncates output to `"ik"`. (The prior session's `max_length` finding was
real but secondary — it only bites on long verses.)

Fix, three changes in `_generate()`:
1. **`num_beams=1` (greedy)** — the decisive fix; removes the early-stopping truncation.
2. **`max_new_tokens=256`** instead of `max_length` in `generate()` — output budget.
3. **`input_max_length` (~1024)** separate from output budget — ByT5 is byte-level
   (512 bytes ≈ 170 Devanagari chars), so long verses need a larger input window.

Verified after fix (greedy): every test verse splits correctly, and the SLM task emits
segmentation + lemma + morphology + root in one call:
```
इक्ष्वाकुवंशप्रभवो रामो नाम जनैः श्रुतः
  → ikṣvāku·vaṃśa·prabhavaḥ·rāmaḥ·nāma·janaiḥ·śrutaḥ
  → …·śrutaḥ_śru_SNPaM   (participle lemmatized to √śru)
```
Latency (MPS, warm): task S ≈ 0.9-1.3 s, task SLM ≈ 2-3 s per verse. Acceptable for the
interactive deep_read path (non-realtime, single verse, no network round-trip). Cold
model load ~1.9 s — keep the engine resident. Full-corpus batch is an offline
pre-compute, out of scope for the live path.

---

## 4. Ranking / disambiguation

Kosha correctly returns *multiple* real candidates for genuine homographs
(`uvāca → {vac, brū}`, `babhūva → {bhū, as}`) and misfires on nominal/verbal homographs
(`रामः` parses as `rā-maḥ`, √rā + 1pl ending, and today sorts above the noun राम because
`analyze_word` unconditionally puts finite verbs first — `kosha_engine.py:434`).

Two-tier predicate:
- **Tier 1 (ByT5 present, preferred):** use the ByT5 SLM POS tag as the ranking prior.
  ByT5 tags `रामः → rāma_SNM` (noun), so ranking kosha candidates to match ByT5's POS
  fixes रामः for free.
- **Tier 2 (kosha-only fallback):** replace unconditional verb-first with — *demote a
  finite-verb reading built on a 1-2 char root (rā, i, as, ā) when a valid subanta
  (nominal) reading exists*; longer roots (gam, bhū) keep verb-first, so गच्छति/जगाम are
  unaffected. A hard "-aḥ can't be a verb" rule is wrong (verbal -vaḥ/-maḥ/-taḥ endings
  exist) and must not be used.

Ranking is explicitly a *separate layer* from segmentation. Semantic plausibility of a
compound (tatpuruṣa vs bahuvrīhi, incoherent-but-lexically-valid concatenations) is a
known residual that hands off to the existing embedding/RAG layer — out of scope here.

---

## 5. Dharmamitra excision

Two independent surfaces (Agent B's map):

**Surface A — dead ensemble engine (default OFF, delete):**
- `engines/dharmamitra_engine.py` (233 lines) + `tests/test_engines/test_dharmamitra_engine.py` → **delete**.
- `analyzer.py:180-188` (conditional registration) + `:216` (weight arg) → delete.
- `engines/ensemble.py:14,100` + docstring `:73-79` (weight field/dict/docstring) → delete/update.
- `config.py:52-55` (dharmamitra* fields) + `:76-77,92-95` (validation) → delete.
- Cosmetic text: `__init__.py:6`, `api/routes/health.py:62`, `api/routes/analyze.py:31`,
  `engines/local_byt5_engine.py:34`.
- Test updates: `test_config.py:30,52-53,196,205`; `test_analyzer/test_analyzer.py:43-47,59,361,409,502-506`.

**Surface B — live HTTP segmenter (default ON, replace body):**
- `deep_read/dharmamitra_segmenter.py` (163 lines) — the live `dharmamitra.org` client.
  Replace its `segment()` **body** with the local pipeline (§2). Keep the module as the
  pluggable seam.
- `deep_read/facade.py:26,159-200` — repoint the `segment()` call to the local pipeline;
  **keep the kosha-enrichment loop and the public `analyze_via_dharmamitra` method
  signature verbatim** (external callers, e.g. the ramayanam controller, depend on it).
  Reword `_DHARMAMITRA_NOTES`.
- Rewrite `tests/test_deep_read/test_dharmamitra_segmenter.py` against the local pipeline
  (now fully offline — drop the network gate).

**Interface contract the local pipeline must honor** (unchanged for consumers):
```
segment(text_devanagari: str) -> list[str] | None
   # → list of unsandhied words (IAST). [] for empty input. None = unavailable → caller
   #   falls back to local kosha engine. MUST NOT raise.
iast_to_devanagari(word: str) -> str
```
Everything downstream (dhātu/lemma/morphology via `kosha_engine.analyze_word`) is already
local and untouched.

---

## 6. Module layout

New package `sanskrit_analyzer/dhatu/`:
```
dhatu/
  identifier.py     DhatuIdentifier: front door. detect_script → to_devanagari →
                    segment → per-segment kosha lookup → rank. Returns extended DhatuInfo.
  segmenter.py      SegmenterPort + implementations:
                      - RuleSegmenter  (Tier 0-2: de-sandhi + Splitter.from_csv + kosha DP)
                      - ByT5Segmenter  (Tier 3: fixed local ByT5, greedy)
                      - WhitespaceSegmenter (Tier 1 floor)
  desandhi.py       Tier-0 reverse-sandhi normalizer (H→s/r, M→m, o→as, devoicing).
  ranking.py        candidate ranking predicate (§4).
```
- **Extend `models/dhatu.py` `DhatuInfo`** to carry form-level morphology
  (lākara/puruṣa/vacana), `source`, and `confidence`.
- **Reuse verbatim:** `deep_read/kosha_engine.py` (`analyze_word`, transliteration
  helpers, `desandhi_candidates`), `utils/normalize.py`, `utils/script_routing.py`,
  `utils/transliterate.py`.
- **Fix in place:** `engines/local_byt5_engine.py:188-193` (§3). Also refactor
  `engines/vidyut_engine.py` to read structured `.data` fields instead of brittle
  `str()`-matching (opportunistic, since it's adjacent).

**Data / CI:** `~/.vidyut-data` (77 MB: kosha 75M, sandhi 16K, prakriya 224K, cheda 2.2M)
and the cached ByT5 must be pre-seeded build/CI artifacts. `vidyut.download_data()` hits
the network on first run — never rely on it at runtime (air-gapped/CI boxes fail otherwise).

---

## 7. Build sequence

**Phase 1 — excise dead Surface A** (zero behavior change, default-off):
delete engine + tests, strip config/ensemble/analyzer wiring, fix asserts, cosmetic text.
`uv run pytest` green. Commit. Isolated, reviewable.

**Phase 2 — fix ByT5** (`_generate` greedy + token budgets, §3). Add offline unit tests
on the cached model asserting correct splits on the three canonical verses. Commit.

**Phase 3 — build the local pipeline** (`dhatu/` package, §6): de-sandhi → Splitter+kosha
DP → ByT5 reranker → ranking. TDD each tier against gold Rāmāyaṇa tokens.

**Phase 4 — replace Surface B**: repoint `facade` / `dharmamitra_segmenter.segment()` to
the local pipeline; keep the seam + public method + enrichment loop. Rewrite the
segmenter test offline. `test_facade.py` (already `use_dharmamitra=False`) stays green
throughout.

**Phase 5 — validate** against the Round-1 `test_ramayanam.py` harness: target ≥90%
gold-token recall on BālaKāṇḍa 1.1.1-1.1.3; full suite (~755 tests) green.

---

## 8. Success criteria

- No code path reaches `dharmamitra.org` or imports `dharmamitra_sanskrit_grammar`.
- `DhatuIdentifier.identify()` works fully offline (Vidyut data + cached ByT5 only).
- ≥90% gold-token recall on the Rāmāyaṇa 1.1 test slokas (rules+ByT5).
- रामः resolves to the nominal राма (not √rā); गच्छति/जगाम unaffected.
- Full test suite (~755) green; segmenter tests run offline with no network gate.

## 9. Out of scope (v1)

- Full-corpus batch pre-compute of segmentations.
- Semantic compound-relation typing (tatpuruṣa/bahuvrīhi/dvandva classification).
- Prakriyā-generated reverse index (kosha already covers it; niche gap-filler only).
- Retraining/fine-tuning any model — we only fix generation config.

---

## 10. As-built deltas (post-implementation, 2026-07-12)

The sections above are the *design*. Implementation diverged; this section is the
authoritative record of what actually shipped.

**Module layout (simpler than §6).** No `SegmenterPort` class hierarchy, no
`desandhi.py`, no `ranking.py`. As-built `sanskrit_analyzer/dhatu/`:
- `segmenter.py` — module-level functions (`segment`, `segment_slp`, `_solve`
  memoized DP). De-sandhi is **reused** from `kosha_engine.desandhi_candidates`,
  not a new module.
- `identifier.py` — `DhatuIdentifier` (injectable `segment_fn`/`pos_hint_fn`,
  plus `DhatuIdentifier.with_byt5()`) returning `TokenResult`; `rank_analyses`
  lives here, not in a separate `ranking.py`.
- `byt5_ranker.py` — `ByT5Adapter` (lazy segment + POS hint over the fixed
  `LocalByT5Engine`).
- `models/dhatu.py` `DhatuInfo` was **not** extended; `vidyut_engine.py` was
  **not** refactored (both deferred — not needed for the deliverable).

**ByT5 is wired and default-on (matches §2/§3 "ships in v1").**
`DeepRead().analyze(text)` uses ByT5 for segmentation + POS ranking by default
(engine label `byt5+kosha`), loaded once per process via
`byt5_ranker.get_shared_adapter()`. `use_byt5=False` selects the fast rule path;
either way it degrades to the rule path automatically when the model is absent
(so CI without the 2 GB model stays green). `DhatuIdentifier.with_byt5()` is the
standalone entry point. Cost when active: ~2 s/verse + a ~2 GB resident model.

**Surface B: deleted, not gutted (§5 said keep the module).**
`deep_read/dharmamitra_segmenter.py` and its test were **removed** entirely (only
`facade.py` imported it). `facade.py` calls `dhatu.segmenter.segment` directly;
IAST→Devanagari uses `engine.to_devanagari(engine.slp(w, "Iast"))` (the old
`iast_to_devanagari` helper is gone). Back-compat kept: `use_dharmamitra` param
(alias for `use_segmenter`) and `analyze_via_dharmamitra` (alias for
`analyze_via_segmenter`).

**Ranking site changed (§4 cited `kosha_engine.py:434`).** `kosha_engine` is
unchanged; ranking is `dhatu.identifier.rank_analyses`, applied in the facade
after `analyze_word`. `रामः` resolves to `derived`/√ram (correct etymology; the
spurious short-root finite verb √rā is suppressed) — not literally the
`nominal`/राम label §8 named.

**Recall criterion (§8 target ≥90%) — NOT met on the strict eval; measured.** A
cross-verse gold-stem eval on BālaKāṇḍa 1.1.1–1.1.3
(`scratchpad/recall_eval.py`): **rules 66%, ByT5 72%.** Much of the gap is
gold-granularity mismatch (gold uses compound-level stems like `satyavākya`/
`dharmajña`, which ByT5 correctly splits into members, so the compound stem is
absent) plus the known rule-DP compound failures the debate predicted
(मुनिपुंगवम् → mu+nipuM+gavam). ByT5 beats rules; both run fully offline. The
90% figure was aspirational and is not substantiated by this eval — treat 66/72%
as the honest baseline and improve segmentation granularity + ranking to raise it.

**Verification.** Full suite **737 passed, 22 skipped, 0 failures**; new coverage
in `tests/test_dhatu/` (segmenter, identifier, ranking, ByT5 adapter) + the ByT5
`_generate` fix test. Zero references to `dharmamitra.org` /
`dharmamitra_sanskrit_grammar`. Nothing committed (no-auto-commit rule).
