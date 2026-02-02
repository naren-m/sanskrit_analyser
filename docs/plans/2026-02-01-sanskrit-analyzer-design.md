# Sanskrit Analyzer - Design Document

**Date:** 2026-02-01
**Status:** Approved
**Author:** Collaborative Design Session

---

## 1. Executive Summary

A centralized Sanskrit sentence parser and analyzer that consolidates existing tools (Vidyut, Dharmamitra ByT5, Sanskrit Heritage Engine) into a unified library with a visual debugging interface.

### Goals
- Parse Sanskrit sentences into hierarchical trees (Sentence → Sandhi Groups → Base Words → Dhatus)
- Provide multiple analysis modes: Academic, Educational, Production
- Handle ambiguity with all valid parses + interactive disambiguation
- Usable as Python library AND REST API
- Visual UI for debugging and disambiguation

### Key Decisions
| Decision | Choice |
|----------|--------|
| Tree structure | 4-level: Sentence → Sandhi → Words → Dhatus |
| Ambiguity handling | All valid parses + interactive disambiguation |
| Disambiguation | Hybrid: Rules → LLM → Human override |
| Analysis engines | 3-engine ensemble (Vidyut, Dharmamitra, Heritage) |
| UI framework | Vue 3 + Cytoscape.js |
| Distribution | Python package + Optional REST API |
| Caching | Tiered: Memory → Redis → SQLite |

---

## 2. System Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                      sanskrit-analyzer                               │
├─────────────────────────────────────────────────────────────────────┤
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐              │
│  │   Vidyut    │    │ Dharmamitra │    │  Heritage   │              │
│  │  (Paninian) │    │   (ByT5)    │    │  (Lexicon)  │              │
│  └──────┬──────┘    └──────┬──────┘    └──────┬──────┘              │
│         │                  │                  │                      │
│         └────────────┬─────┴──────────────────┘                      │
│                      ▼                                               │
│         ┌────────────────────────┐                                   │
│         │   Ensemble Combiner    │◄── Confidence weighting           │
│         │   (Vote + Merge)       │◄── Conflict resolution            │
│         └───────────┬────────────┘                                   │
│                     ▼                                                │
│         ┌────────────────────────┐                                   │
│         │    Parse Tree Builder  │──► 4-level hierarchy              │
│         └───────────┬────────────┘                                   │
│                     ▼                                                │
│         ┌────────────────────────┐                                   │
│         │  Disambiguation Layer  │◄── Rules → LLM → Human            │
│         └───────────┬────────────┘                                   │
│                     ▼                                                │
│    ┌────────────────────────────────────────┐                        │
│    │         Tiered Cache                   │                        │
│    │  [Memory LRU] → [Redis] → [SQLite]     │                        │
│    └────────────────────────────────────────┘                        │
├─────────────────────────────────────────────────────────────────────┤
│  Interfaces:  Python Library  │  REST API  │  Vue+Cytoscape UI       │
└─────────────────────────────────────────────────────────────────────┘
```

### Core Flow
1. Input sentence → Normalize script (Devanagari/IAST/SLP1)
2. Check tiered cache for existing analysis
3. Run three engines in parallel
4. Combine results via ensemble voting
5. Build 4-level parse tree (Sentence → Sandhi → Words → Dhatus)
6. Apply disambiguation pipeline if ambiguous
7. Cache result at all tiers
8. Return structured tree + confidence metrics

---

## 3. Data Structures

### 3.1 Analysis Tree

```python
@dataclass
class AnalysisTree:
    """Root container for a complete sentence analysis"""
    sentence_id: str
    original_text: str                    # Raw input
    normalized_slp1: str                  # Normalized to SLP1
    scripts: ScriptVariants               # All script representations
    parse_forest: List[ParseTree]         # All valid parses (ambiguity)
    selected_parse: Optional[int]         # Index of disambiguated choice
    confidence: ConfidenceMetrics
    mode: AnalysisMode                    # ACADEMIC | EDUCATIONAL | PRODUCTION
    cached_at: Optional[CacheTier]        # MEMORY | REDIS | SQLITE

@dataclass
class ParseTree:
    """One complete parse of the sentence"""
    parse_id: str
    confidence: float                     # 0.0 - 1.0
    engine_votes: Dict[str, float]        # {"vidyut": 0.9, "dharmamitra": 0.85, ...}
    sandhi_groups: List[SandhiGroup]      # Level 2

@dataclass
class SandhiGroup:
    """A sandhi-joined unit (may be single word or compound)"""
    surface_form: str                     # As it appears in text
    scripts: ScriptVariants
    sandhi_type: Optional[SandhiType]     # SAVARNA_DIRGHA | GUNA | VRDDHI | YAN | VISARGA
    sandhi_rule: Optional[str]            # Ashtadhyayi sutra reference
    is_compound: bool
    compound_type: Optional[str]          # TATPURUSHA | DVANDVA | BAHUVRIHI | AVYAYIBHAVA
    base_words: List[BaseWord]            # Level 3

@dataclass
class BaseWord:
    """Individual word after sandhi splitting"""
    lemma: str                            # Dictionary form
    surface_form: str                     # Form in this context
    scripts: ScriptVariants
    morphology: MorphologicalTag          # Case, gender, number, person, tense...
    meanings: List[Meaning]               # From dictionary lookup
    dhatu: Optional[DhatuInfo]            # Level 4 (if verb-derived)
    pratyaya: List[Pratyaya]              # Suffixes applied
    upasarga: List[str]                   # Prefixes (pra-, upa-, etc.)

@dataclass
class DhatuInfo:
    """Verbal root information"""
    dhatu: str                            # Root form (e.g., गम्, कृ)
    scripts: ScriptVariants
    gana: int                             # 1-10
    pada: str                             # PARASMAIPADA | ATMANEPADA | UBHAYAPADA
    meanings: List[str]                   # Primary meanings
    prakriya: Optional[List[str]]         # Derivation steps (from Vidyut)
```

### 3.2 Supporting Types

```python
@dataclass
class ScriptVariants:
    devanagari: str
    iast: str
    slp1: str

class AnalysisMode(Enum):
    PRODUCTION = "production"      # Fast, single-best
    EDUCATIONAL = "educational"    # Includes prakriya
    ACADEMIC = "academic"          # All details

class SandhiType(Enum):
    SAVARNA_DIRGHA = "savarṇa-dīrgha"
    GUNA = "guṇa"
    VRDDHI = "vṛddhi"
    YAN = "yāṇ"
    VISARGA = "visarga"

@dataclass
class ConfidenceMetrics:
    overall: float
    engine_agreement: float
    disambiguation_applied: bool
```

---

## 4. Ensemble Engine Architecture

### 4.1 Engine Configuration

| Engine | Weight | Strength |
|--------|--------|----------|
| Vidyut | 0.35 | Paninian rules, prakriya generation |
| Dharmamitra ByT5 | 0.40 | Neural morphosyntax, handles OOV |
| Sanskrit Heritage | 0.25 | 25K lexicon, finite-state sandhi |

### 4.2 Voting Strategy

| Scenario | Resolution |
|----------|------------|
| All 3 agree | High confidence (0.95+), use consensus |
| 2 of 3 agree | Medium confidence (0.7-0.9), use majority |
| All 3 differ | Low confidence (< 0.7), flag for disambiguation |
| Engine error | Degrade gracefully, use remaining engines |

### 4.3 Task-Specific Engine Priority

| Task | Primary | Fallback |
|------|---------|----------|
| Sandhi splitting | Vidyut | Heritage |
| Lemmatization | Dharmamitra | Heritage |
| Morphological tags | Dharmamitra | Vidyut |
| Dhatu identification | Vidyut | Dhatu DB |
| Unknown words | Dharmamitra | — |
| Compound analysis | Heritage + Vidyut | Dharmamitra |

### 4.4 Implementation

```python
class EnsembleAnalyzer:
    def __init__(self):
        self.engines = {
            "vidyut": VidyutEngine(),
            "dharmamitra": DharmamitraEngine(),
            "heritage": HeritageEngine()
        }
        self.weights = {"vidyut": 0.35, "dharmamitra": 0.40, "heritage": 0.25}

    async def analyze(self, text: str) -> List[EngineResult]:
        results = await asyncio.gather(
            self.engines["vidyut"].analyze(text),
            self.engines["dharmamitra"].analyze(text),
            self.engines["heritage"].analyze(text),
            return_exceptions=True
        )
        return results
```

---

## 5. Disambiguation Pipeline

```
Parse Forest (N candidates)
        │
        ▼
┌──────────────────┐
│  Stage 1: RULES  │  Deterministic filters
│  ─────────────── │
│  • Grammatical   │  Reject impossible combinations
│    constraints   │  (e.g., neuter noun + feminine adj)
│  • Frequency     │  Prefer common forms over rare
│    ranking       │
│  • Context       │  Use surrounding verse/commentary
│    heuristics    │
└────────┬─────────┘
         │ (if still ambiguous)
         ▼
┌──────────────────┐
│  Stage 2: LLM    │  Semantic understanding
│  ─────────────── │
│  • Present top   │  "Which parse makes sense here?"
│    candidates    │
│  • Include       │  Verse context, commentary hints
│    context       │
│  • Ask Claude/   │  Returns ranked preference
│    Ollama        │
└────────┬─────────┘
         │ (if confidence < threshold OR user requests)
         ▼
┌──────────────────┐
│  Stage 3: HUMAN  │  Final authority via UI
│  ─────────────── │
│  • Visual tree   │  Cytoscape graph of options
│    comparison    │
│  • Click to      │  Selection saved to corpus
│    select        │
│  • Feedback      │  Improves future rule weights
│    loop          │
└──────────────────┘
```

### 5.1 Rule Examples

```python
DISAMBIGUATION_RULES = [
    ("adj_noun_agreement", weight=0.9),
    ("verb_subject_agreement", weight=0.85),
    ("prefer_common_sandhi", weight=0.6),
    ("prefer_shorter_compounds", weight=0.4),
    ("verse_meter_fit", weight=0.7),
    ("commentary_hint", weight=0.8),
]
```

### 5.2 LLM Prompt Template

```
Given this Sanskrit text: {text}
Context: {verse_context}

Candidate parses:
1. {parse_1_summary} (confidence: {conf_1})
2. {parse_2_summary} (confidence: {conf_2})

Which interpretation is most likely correct and why?
```

---

## 6. Tiered Caching

```
analyze("रामो गच्छति")
       │
       ▼
┌─────────────┐   HIT
│  Memory LRU │ ─────────► Return immediately (<1ms)
│  (1K items) │
└──────┬──────┘
       │ MISS
       ▼
┌─────────────┐   HIT
│    Redis    │ ─────────► Promote to Memory, return (~5ms)
│  (TTL: 7d)  │
└──────┬──────┘
       │ MISS
       ▼
┌─────────────┐   HIT
│   SQLite    │ ─────────► Promote to Redis+Memory (~20ms)
│ (permanent) │
└──────┬──────┘
       │ MISS
       ▼
┌─────────────┐
│  Ensemble   │ ─────────► Analyze, store in ALL tiers
│  Analysis   │            (~200-500ms)
└─────────────┘
```

### 6.1 SQLite Corpus Schema

```sql
CREATE TABLE analyses (
    id TEXT PRIMARY KEY,
    original_text TEXT NOT NULL,
    normalized_slp1 TEXT NOT NULL,
    mode TEXT NOT NULL,
    result_json TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    accessed_at TIMESTAMP,
    access_count INTEGER DEFAULT 1,
    disambiguated BOOLEAN DEFAULT FALSE,
    selected_parse INTEGER
);

CREATE INDEX idx_text ON analyses(normalized_slp1);
CREATE INDEX idx_accessed ON analyses(accessed_at);

CREATE VIRTUAL TABLE analyses_fts USING fts5(
    original_text,
    content=analyses
);
```

---

## 7. Library & API Design

### 7.1 Python Library

```python
from sanskrit_analyzer import Analyzer, AnalysisMode

analyzer = Analyzer(
    engines=["vidyut", "dharmamitra", "heritage"],
    cache_tiers=["memory", "redis", "sqlite"],
    redis_url="redis://localhost:6379",
    db_path="~/.sanskrit_analyzer/corpus.db"
)

# Simple analysis
result = analyzer.analyze("तपःस्वाध्यायेश्वरप्रणिधानानि क्रियायोगः")

# Access the tree
for sandhi_group in result.best_parse.sandhi_groups:
    print(f"{sandhi_group.surface_form} ({sandhi_group.sandhi_type})")
    for word in sandhi_group.base_words:
        print(f"  └─ {word.lemma}: {word.meanings[0]}")
        if word.dhatu:
            print(f"      └─ √{word.dhatu.dhatu} ({word.dhatu.gana})")

# Get all parses
result = analyzer.analyze("रामो गच्छति", return_all_parses=True)

# Different modes
result = analyzer.analyze(text, mode=AnalysisMode.PRODUCTION)
result = analyzer.analyze(text, mode=AnalysisMode.EDUCATIONAL)
```

### 7.2 REST API

```
POST /api/v1/analyze
  Body: {"text": "...", "mode": "academic", "return_all_parses": true}
  Response: AnalysisTree JSON

GET  /api/v1/analyze/{sentence_id}
  → Cached analysis by ID

POST /api/v1/disambiguate
  Body: {"sentence_id": "...", "selected_parse": 2}
  → Save disambiguation choice

GET  /api/v1/dhatu/{dhatu}
  → Dhatu lookup with meanings, gana, forms

GET  /api/v1/dictionary/{word}
  → Dictionary lookup with morphological analysis

WebSocket /ws/analyze
  → Streaming analysis for long texts
```

---

## 8. Vue + Cytoscape UI

### 8.1 Mockup

```
┌─────────────────────────────────────────────────────────────────────────┐
│  Sanskrit Analyzer                                        [Mode: ▼ All] │
├─────────────────────────────────────────────────────────────────────────┤
│ Input: [तपःस्वाध्यायेश्वरप्रणिधानानि क्रियायोगः________________] [Analyze]│
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌─ Parse Tree (3 candidates) ──────────────────────────────────────┐  │
│  │                     ┌──────────────┐                              │  │
│  │                     │   Sentence   │                              │  │
│  │                     └──────┬───────┘                              │  │
│  │             ┌──────────────┼──────────────┐                       │  │
│  │             ▼              ▼              ▼                       │  │
│  │      ┌──────────┐   ┌──────────┐   ┌──────────┐                  │  │
│  │      │ Sandhi 1 │   │ Sandhi 2 │   │ Sandhi 3 │                  │  │
│  │      └────┬─────┘   └────┬─────┘   └────┬─────┘                  │  │
│  │           │              │              │                         │  │
│  │      ┌────┴────┐         │         ┌────┴────┐                    │  │
│  │      ▼         ▼         ▼         ▼         ▼                    │  │
│  │   [Word]   [Word]     [Word]    [Word]    [Word]                  │  │
│  │      │         │         │         │                              │  │
│  │      ▼         ▼         ▼         ▼                              │  │
│  │   √dhatu   √dhatu     √dhatu    √dhatu                            │  │
│  └───────────────────────────────────────────────────────────────────┘  │
│                                                                         │
├─────────────────────────────────────────────────────────────────────────┤
│  Selected Node: [क्रिया]                                                │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │ Lemma: क्रिया (kriyā)           Morphology: f. nom. sg.         │   │
│  │ Dhatu: √कृ (kṛ) - gana 8        Meaning: action, doing, rite    │   │
│  │ Pratyaya: क्यप् (kyap)          Engines: V:0.9 D:0.88 H:0.85    │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                                                         │
│  [◀ Prev Parse]  Parse 1 of 3  [Next Parse ▶]    [✓ Select This Parse] │
└─────────────────────────────────────────────────────────────────────────┘
```

### 8.2 UI Features

| Feature | Purpose |
|---------|---------|
| Zoomable tree | Cytoscape pan/zoom for large sentences |
| Node click | Shows detailed analysis in bottom panel |
| Color coding | Green=high conf, Yellow=medium, Red=ambiguous |
| Parse navigation | Flip through all valid parses |
| Disambiguation | "Select This Parse" saves to corpus |
| Script toggle | Switch between Devanagari/IAST/SLP1 |
| Mode selector | Academic / Educational / Production |
| Export | JSON, SVG tree image, PDF report |

---

## 9. Project Structure

```
sanskrit_analyzer/
├── pyproject.toml
├── README.md
├── LICENSE
│
├── sanskrit_analyzer/
│   ├── __init__.py
│   ├── analyzer.py
│   ├── config.py
│   │
│   ├── engines/
│   │   ├── __init__.py
│   │   ├── base.py
│   │   ├── vidyut_engine.py
│   │   ├── dharmamitra_engine.py
│   │   ├── heritage_engine.py
│   │   └── ensemble.py
│   │
│   ├── models/
│   │   ├── __init__.py
│   │   ├── tree.py
│   │   ├── morphology.py
│   │   ├── dhatu.py
│   │   └── scripts.py
│   │
│   ├── disambiguation/
│   │   ├── __init__.py
│   │   ├── rules.py
│   │   ├── llm.py
│   │   └── pipeline.py
│   │
│   ├── cache/
│   │   ├── __init__.py
│   │   ├── memory.py
│   │   ├── redis_cache.py
│   │   ├── sqlite_corpus.py
│   │   └── tiered.py
│   │
│   ├── data/
│   │   ├── dhatu_database.db
│   │   ├── sandhi_rules.yaml
│   │   └── gana_map.yaml
│   │
│   └── utils/
│       ├── __init__.py
│       ├── transliterate.py
│       └── normalize.py
│
├── api/
│   ├── __init__.py
│   ├── app.py
│   ├── routes/
│   │   ├── analyze.py
│   │   ├── dhatu.py
│   │   └── dictionary.py
│   └── websocket.py
│
├── ui/
│   ├── package.json
│   ├── vite.config.ts
│   ├── src/
│   │   ├── App.vue
│   │   ├── components/
│   │   │   ├── ParseTree.vue
│   │   │   ├── NodeDetail.vue
│   │   │   └── InputBar.vue
│   │   └── stores/
│   │       └── analysis.ts
│   └── public/
│
├── tests/
│   ├── test_engines/
│   ├── test_ensemble/
│   ├── test_disambiguation/
│   └── fixtures/
│
└── examples/
    ├── basic_usage.py
    ├── batch_analysis.py
    └── integrate_ramayanam.py
```

---

## 10. Configuration

### 10.1 Config File (`~/.sanskrit_analyzer/config.yaml`)

```yaml
engines:
  vidyut:
    enabled: true
    weight: 0.35
    prakriya_depth: full

  dharmamitra:
    enabled: true
    weight: 0.40
    model: "buddhist-nlp/byt5-sanskrit"
    batch_size: 10
    device: auto

  heritage:
    enabled: true
    weight: 0.25
    mode: local
    local_url: "http://localhost:8080"
    lexicon_path: "~/.sanskrit_analyzer/heritage_lexicon.db"

cache:
  memory:
    enabled: true
    max_size: 1000
  redis:
    enabled: true
    url: "redis://localhost:6379/0"
    ttl_days: 7
  sqlite:
    enabled: true
    path: "~/.sanskrit_analyzer/corpus.db"

disambiguation:
  rules:
    enabled: true
    min_confidence_skip: 0.95
  llm:
    enabled: true
    provider: ollama
    model: "llama3.2"
    ollama_url: "http://localhost:11434"
  human:
    enabled: true
    auto_prompt: false

modes:
  production:
    return_all_parses: false
    include_prakriya: false
    max_candidates: 1
  educational:
    return_all_parses: true
    include_prakriya: true
    max_candidates: 5
  academic:
    return_all_parses: true
    include_prakriya: true
    include_engine_details: true
    max_candidates: -1

scripts:
  default_output: devanagari
  input_detection: auto

logging:
  level: INFO
  file: "~/.sanskrit_analyzer/logs/analyzer.log"
```

---

## 11. Heritage Engine Integration

### 11.1 Approach: Docker + Cached Lexicon

```python
class HeritageEngine(EngineBase):
    def __init__(self, config: HeritageConfig):
        self.local_url = config.local_url or "http://localhost:8080"
        self.public_url = "https://sanskrit.inria.fr/cgi-bin/SKT"
        self.lexicon = self._load_cached_lexicon()
        self.use_local = config.use_local_container

    async def analyze(self, text: str) -> EngineResult:
        slp1_text = transliterate(text, to="slp1")

        try:
            if self.use_local:
                result = await self._query_local(slp1_text)
            else:
                result = await self._query_public(slp1_text)
            return self._parse_heritage_response(result)
        except HeritageUnavailable:
            return self._lexicon_fallback(slp1_text)
```

### 11.2 Docker Setup

```yaml
services:
  heritage-engine:
    image: sanskrit-heritage:latest
    build:
      context: .
      dockerfile: Dockerfile.heritage
    ports:
      - "8080:80"
    volumes:
      - ./lexicon:/app/data
```

---

## 12. Implementation Phases

### Phase 1: Core Foundation
- Set up package structure
- Port data models from ramayanam
- Wrap Vidyut and Dharmamitra as engines
- Basic Analyzer class
- Unit tests
- **Deliverable:** Basic analysis works

### Phase 2: Ensemble & Caching
- Implement ensemble voting
- Add tiered cache (memory + SQLite + Redis)
- Port dhatu database
- Integration tests
- **Deliverable:** Two-engine ensemble with caching

### Phase 3: Heritage Integration
- Docker container for Heritage Engine
- HeritageEngine wrapper
- Extract and cache lexicon
- Three-engine ensemble
- **Deliverable:** Full ensemble, production-ready library

### Phase 4: Disambiguation Pipeline
- Rule-based filters
- LLM disambiguation (Ollama)
- Human override model
- Corpus with disambiguation storage
- **Deliverable:** Complete analysis pipeline

### Phase 5: REST API
- FastAPI application
- All endpoints
- WebSocket streaming
- OpenAPI docs
- **Deliverable:** API server deployable

### Phase 6: Vue UI
- Vue 3 + Vite setup
- Cytoscape tree visualization
- Node detail panel
- Disambiguation UI
- **Deliverable:** Visual debugging interface

---

## 13. Migration Path

### From Existing Projects

```python
# BEFORE (ramayanam - scattered)
from api.services.dharmamitra_service import analyze_morphology
from api.services.sandhi_service import split_sandhi
from api.services.dictionary_service import lookup_meaning

def analyze_verse(text):
    morphology = analyze_morphology(text)
    sandhi = split_sandhi(text)
    meanings = [lookup_meaning(w) for w in sandhi]
    return combine_results(morphology, sandhi, meanings)

# AFTER (unified)
from sanskrit_analyzer import Analyzer

analyzer = Analyzer.from_config()

def analyze_verse(text):
    return analyzer.analyze(text, mode=AnalysisMode.PRODUCTION)
```

### Backward Compatibility
- Keep old services as thin wrappers initially
- Gradually migrate callers
- Feature flag to switch between old/new

---

## 14. References

### Tools & Libraries
- [Vidyut](https://github.com/ambuda-org/vidyut) - Paninian grammar, ~2000 Ashtadhyayi rules
- [Dharmamitra ByT5](https://github.com/sebastian-nehrdich/byt5-sanskrit-analyzers) - Neural morphosyntax
- [Sanskrit Heritage Engine](https://sanskrit.inria.fr/) - Gérard Huet's lexicon + FST
- [SanskritShala](https://github.com/Jivnesh/SanskritShala) - Neural NLP toolkit

### Research
- [Sandarśana: Survey on Sanskrit Computational Linguistics](https://dl.acm.org/doi/10.1145/3729530)
- [7th ISCLS 2024 Proceedings](https://iscls.github.io/)
- [Sanskrit Segmentation Revisited](https://arxiv.org/abs/2005.06383)

---

## 15. Open Questions

1. **Heritage Engine licensing** - Need to verify redistribution terms for Docker image
2. **LLM fallback** - Should we support multiple LLM providers (Ollama, Claude, OpenAI)?
3. **Corpus sharing** - Should disambiguated analyses be shareable across users?
4. **Vedic support** - Current focus is Classical Sanskrit; Vedic accent marks need consideration

---

*Document generated through collaborative brainstorming session.*
