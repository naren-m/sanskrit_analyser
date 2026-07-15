# Prakriyā Engine — Design Document
### A verse-to-dhātu analyzer with full Pāṇinian rule tracing

**Goal.** Given any Sanskrit input — a śloka, sūtra, stuti line, or prose sentence — produce a complete structural understanding down to the dhātu level: sentence split, sandhi-resolved word split, chandas identification with meter name, per-word morphological analysis (dhātu / prātipadika, pratyaya chain, vibhakti/lakāra), word meaning, and **every Aṣṭādhyāyī sūtra applied, cited by number with sūtra text and Kāśikā gloss**. Translation is explicitly out of scope; understanding is the deliverable.

---

## 1. The core architectural idea: Analysis by Synthesis

Direct reverse-engineering of Pāṇini (running sūtras backwards) is intractable — the Aṣṭādhyāyī is a generative device, not a parser. The tractable and *provably correct* approach is:

1. **Propose** candidate analyses (segmentations + morphological hypotheses) using fast lookup/statistical methods.
2. **Verify** each hypothesis by *forward-generating* it through a Pāṇinian engine (**vidyut-prakriya**).
3. If the generated surface form matches the observed word, the generation's **step-by-step rule trace is the proof** — and it is exactly the sūtra-by-sūtra derivation the user wants to display.

This means the rule citations are never heuristic annotations: they are the actual derivation log of a verified prakriyā. This is the same Layer-A verification discipline already adopted in the vyutpatti resource, extended from single names to full verses.

```
Input verse
   │
   ▼
[1] Normalize (script → SLP1)
   │
   ▼
[2] Verse/pāda segmentation ──────► [3] Chandas identifier (meters.tsv)
   │
   ▼
[4] Sandhi-split lattice (rules.csv inverted + segmenter)
   │
   ▼
[5] Morphological hypothesis generation (vidyut-kosha lookup)
   │
   ▼
[6] Lattice scoring & disambiguation (DCS-trained LM)
   │
   ▼
[7] Prakriyā verification (vidyut-prakriya forward generation)
   │        └── rule trace: sūtra numbers + text + Kāśikā
   ▼
[8] Semantic layer (dhātvartha, Amarakośa, CDSL glosses)
   │
   ▼
[9] Structured output (JSON) → renderer (CLI / web / notes export)
```

---

## 2. Data assets already in hand (project files)

| File | Role in the system |
|---|---|
| `dhatupatha.tsv` | Canonical dhātu inventory (code, dhātu in SLP1 with svaras/anubandhas, artha). The terminal node of every verbal analysis. |
| `sutrapatha.tsv` | Full Aṣṭādhyāyī (~3,983 sūtras). Lookup table: rule code → sūtra text for display in traces. |
| `kashika.tsv` | Kāśikā vṛtti keyed by sūtra — the explanatory gloss shown alongside each applied rule. |
| `kaumudi.tsv` | Siddhāntakaumudī ordering — optional alternate presentation of the derivation (kaumudī-krama vs. aṣṭādhyāyī-krama). |
| `varttikas.tsv` | Vārttika citations where vidyut applies them. |
| `unadipatha.tsv` | Uṇādi derivations — the join point for nipātana-sanctioned stems (already identified as the Layer A/B bridge). |
| `dhatupatha-ganasutras.tsv` | Gaṇa-sūtras (mit-designation etc.) affecting derivation. |
| `linganushasanam.tsv`, `phit-sutras.tsv` | Gender assignment and accent — used in the nominal analysis annotation layer. |
| `rules.csv` | **Compiled sandhi lookup table** (first, second, result — 1,468 rows). Inverted, it becomes the sandhi *splitter*: index by `result` to propose (first, second) splits. Note: this is euphonics only, not morphology — the morphological grammar lives in vidyut-prakriya itself. |
| `meters.tsv` | 146 meters: name, class (vṛtta/…), and L/G pattern with pāda-boundary `|` markers. Direct driver of the chandas module. |

External (already in the toolchain): **vidyut-prakriya** and **vidyut-kosha/cheda**, **DCS** (~4.8M annotated tokens) for training the disambiguation model, **PyCDSL** for glosses, **Amarakośa** for synonym sets.

---

## 3. Module design

### 3.1 Input normalization
- Detect script (Devanagari, IAST, Telugu, SLP1, HK) via `indic-transliteration` / vidyut-lipi; convert everything to SLP1 internally.
- Strip/record daṇḍas, avagraha (preserve avagraha — it is sandhi evidence: `rAmo 'sti` tells you the split for free), numerals, verse numbers.
- Preserve a character-offset map so every analysis can be highlighted against the original input.

### 3.2 Verse & pāda segmentation
- Split on daṇḍa/double-daṇḍa into half-verses; use the chandas module (below) to hypothesize pāda boundaries when punctuation is absent (common in stuti texts copied from the web).
- Output: verse → pādas → raw sandhied strings.

### 3.3 Chandas identifier
Algorithm (pure function, no ML needed):
1. Syllabify the SLP1 pāda: a syllable = (C*)V(C*); weight = **guru** if vowel is long, or followed by conjunct/anusvāra/visarga, or pāda-final (optionally); else **laghu**.
2. Produce the L/G string per pāda.
3. **Vṛtta matching:** exact/near match against `meters.tsv` patterns (strip `|` markers for comparison; use them to confirm yati). Handle pāda-final anceps (last syllable free).
4. **Jāti/mātrā meters (āryā etc.):** compute mātrā counts per pāda (L=1, G=2) and match against mātrā templates (extend meters.tsv with a jāti table — small addition).
5. **Anuṣṭubh special case:** the śloka is not a fixed L/G template; implement the pathyā/vipulā rules (5th laghu, 6th guru, 7th alternating in even pādas; vipulā variants na/bha/ma/ra) as explicit checks.
6. Output: meter name, gaṇa decomposition (ya-mā-tā-rā-ja-bhā-na-sa-la-gaḥ encoding), per-syllable weight annotation, yati positions, and defects flagged (chandobhaṅga) — useful for detecting corrupt text *before* sandhi analysis wastes effort.
7. Feedback loop: metrical constraints prune sandhi-split candidates (a split implying a different syllable count than the meter allows is penalized). This is exactly where pure-neural systems fail — here the meter is a hard symbolic constraint.

### 3.4 Sandhi splitter
Two engines, merged into one **split lattice**:
- **Table-driven:** invert `rules.csv` — index by `result`, at every character position propose all (first, second) decompositions. Cheap, complete for the covered rules, fully citable (each split carries the sandhi rule that licenses it, and those map to A. 6.1.x sūtras — add a `rules.csv → sūtra code` mapping column as a one-time enrichment task).
- **Lexicon-guided (vidyut-cheda / Heritage-style):** only keep split points where both sides can extend to dictionary-attested padas. This kills the combinatorial explosion.
- Output: a DAG (lattice) whose edges are candidate padas with their licensing sandhi rule.

### 3.5 Morphological hypothesis generation
For each candidate pada in the lattice, query **vidyut-kosha** (precompiled from vidyut-prakriya's generative closure) for all analyses:
- **Tiṅanta:** dhātu code (→ `dhatupatha.tsv` row), gaṇa, lakāra, prayoga, puruṣa, vacana, upasargas, sanādi (ṇic/san/yaṅ).
- **Subanta:** prātipadika, liṅga, vibhakti, vacana.
- **Kṛdanta:** dhātu + kṛt pratyaya (kta, ktavatu, lyuṭ, ghañ, tavya, śatṛ…) → then declined as subanta. This is the main road from nouns back to dhātus.
- **Taddhita peeling:** prātipadika = base + taddhita (aṇ, ṭhak, matup…), recursively, until a dhātu-derived or uṇādi stem is reached.
- **Samāsa:** split compounds (vidyut + heuristics + lexicon), classify (tatpuruṣa/bahuvrīhi/dvandva/avyayībhāva) by vigraha templates; each member re-enters the pipeline.
- **Uṇādi fallback:** stems with no productive derivation get matched to `unadipatha.tsv` entries (nipātana), flagged as such — never silently invent a dhātu connection. Truly underived items (avyayas, deśī words) are labeled honestly.

### 3.6 Disambiguation
A single pada often has 5–50 analyses; a verse lattice can have thousands of paths. Score paths with:
- A **statistical model trained on DCS** (token-level morphological tag LM; even a trigram model over (lemma, tag) pairs gets far; a small transformer scorer is the upgrade path).
- **Hard constraints:** meter compatibility (3.3.7), kāraka/agreement checks (viśeṣaṇa-viśeṣya liṅga/vibhakti/vacana agreement; tiṅanta–kartṛ agreement), sandhi-rule validity.
- Return the top-k full-verse analyses ranked, never just one — scholarly users want to see alternatives (this matches the project's principle of surfacing non-obvious readings).

### 3.7 Prakriyā verification & rule tracing (the heart)
For each surviving analysis:
1. Re-generate the surface form with **vidyut-prakriya** from (dhātu/prātipadika + affix parameters).
2. Match against the observed pada → accept/reject (Layer-A discipline).
3. Capture the derivation history: vidyut exposes each step's rule code. Join each code against `sutrapatha.tsv` (text) + `kashika.tsv` (gloss) + `varttikas.tsv`.
4. Render the prakriyā: `BU → BU + tip (A.3.4.78) → BU + Sap + tip (A.3.1.68) → Bo + a + ti (A.7.3.84 sārvadhātukārdhadhātukayoḥ, guṇa) → Bav + a + ti (A.6.1.78 eco 'yavāyāvaḥ) → Bavati`, each step showing sūtra number, sūtra text (SLP1/Devanagari/IAST as user prefers), and one-line Kāśikā extract.
5. Optionally re-order the same trace in **Kaumudī sequence** using `kaumudi.tsv` for learners trained on SK.
6. Sandhi rules used at word boundaries are cited the same way (from the enriched rules.csv mapping).

### 3.8 Semantic layer
- Dhātvartha directly from `dhatupatha.tsv` (e.g. `BU — sattAyAm`).
- Pada gloss: PyCDSL (MW, Śabdakalpadruma, Vācaspatyam) with source attribution — Layer B rules apply: retrieved, attributed, never conflated with the generative layer.
- Amarakośa synonym set + semantic domain for the prātipadika (also feeds the future embedding work).
- For names in stutis: hook into the existing vyutpatti JSONL records (rāma, rudra, śaṅkara…) so the analyzer and the vyutpatti resource reinforce each other.

### 3.9 Output schema (JSON, one record per verse)
```json
{
  "input": {"raw": "...", "script": "devanagari", "slp1": "..."},
  "chandas": {
    "name": "vasantatilakA", "class": "vrtta",
    "pattern": "GGLGLLLGLLGLGG",
    "ganas": "ta-BA-ja-ja-ga-ga", "yati": [8],
    "pada_scans": [["G","G","L","..."]], "defects": []
  },
  "padas": [
    {
      "surface": "Bavati",
      "sandhi": {"joined_with_next": null, "rule": null},
      "analyses": [
        {
          "rank": 1, "score": 0.94, "verified": true,
          "type": "tinanta",
          "dhatu": {"code": "01.0001", "slp1": "BU", "artha": "sattAyAm", "gana": 1},
          "features": {"lakara": "law", "prayoga": "kartari",
                        "purusha": "prathama", "vacana": "eka"},
          "prakriya": [
            {"step": 1, "form": "BU", "sutra": "3.4.78",
             "sutra_text": "tiptasJisip...", "kashika": "...", "note": "tiN-vidhi"},
            {"step": 4, "form": "Bo a ti", "sutra": "7.3.84",
             "sutra_text": "sArvaDAtukArDaDAtukayoH", "kashika": "...", "note": "guRa"}
          ],
          "gloss": [{"source": "MW", "text": "..."}]
        }
      ]
    }
  ],
  "alternatives": [ "…top-k full-sentence readings…" ]
}
```

---

## 4. Tech stack & repo layout

- **Core:** Rust `vidyut` crates (prakriya, kosha, cheda, lipi, chandas — note vidyut ships a `vidyut-chandas` crate; evaluate it before writing 3.3 from scratch) with Python bindings.
- **Orchestration/API:** Python (FastAPI). CLI first (`prakriya analyze "verse"` → JSON / rich terminal render), web UI second.
- **Disambiguation model:** start with a KenLM/trigram tag model on DCS; upgrade path to a small fine-tuned scorer.
- **Storage:** SQLite for the sūtra/kāśikā/gloss joins; the TSVs load into it at build time (extend the existing `build_vyutpatti.py` scaffold pattern).
- **Renderer:** terminal (rich), HTML report per verse, and an exporter matching the literature-notes YAML-frontmatter + etymology-table format so verified analyses can flow straight into `naren-m/literature-notes`.

```
prakriya-engine/
├── data/            # the project TSVs + enrichments (rules.csv→sūtra map, jāti meters)
├── build/           # loaders → sqlite
├── core/
│   ├── normalize.py
│   ├── chandas.py
│   ├── sandhi_lattice.py
│   ├── morphology.py      # vidyut-kosha wrapper
│   ├── disambiguate.py
│   ├── verify.py          # vidyut-prakriya trace capture
│   └── semantics.py
├── render/          # cli, html, literature-notes exporter
├── api/
└── tests/           # golden verses: BG 2.47, sahasranāma lines, laghu/āryā samples
```

---

## 5. Build order (each phase independently useful)

1. **Phase 1 — Chandas + normalization** (1–2 weeks): pure-function meter identifier over `meters.tsv` + anuṣṭubh logic. Immediately useful standalone; no dependencies.
2. **Phase 2 — Single-pada analyzer**: vidyut-kosha lookup + vidyut-prakriya verification + rule trace rendering with sutrapatha/kāśikā joins. This is the dhātu-drill-down core.
3. **Phase 3 — Sandhi lattice + disambiguation**: rules.csv inversion, lexicon-guided splitting, DCS scoring. Now full verses work.
4. **Phase 4 — Kṛdanta/taddhita/samāsa recursion + uṇādi fallback**: complete the noun→dhātu road.
5. **Phase 5 — Semantics + exporters**: PyCDSL/Amarakośa glossing, literature-notes export, web UI.

Golden-test discipline throughout: a fixed suite of verses with hand-verified expected analyses (start with Gītā verses — DCS has gold annotations to compare against).

---

## 6. Known hard problems (stated honestly)

- **Segmentation ambiguity** is the single hardest problem; the meter constraint + DCS scoring + verification loop is the mitigation, but top-k output (not forced single answers) is the honest design.
- **Vedic/accented text**: vidyut-prakriya targets laukika Sanskrit; svarita/udātta handling and Vedic forms (chandas-only rules, A. 6.4.x vedic options) need a flagged "Vedic mode" later.
- **ārṣa-prayoga in stutis**: devotional texts contain non-Pāṇinian forms; the verifier will (correctly) fail — the UI should say "no Pāṇinian derivation found; nearest analyses:" rather than fabricate one.
- **Samāsa classification** (tatpuruṣa vs. bahuvrīhi) is often context-dependent; present both with vigraha paraphrases.
- **rules.csv scope**: it is euphonics only; do not let it masquerade as morphological coverage (already a settled project principle).
