# Sanskrit Analyzer: MCP Server & Model Training Design

**Date:** 2026-02-02
**Status:** Design Complete, Ready for Implementation

---

## Executive Summary

This document outlines the design for:
1. **MCP Server** - Exposing the Sanskrit Analyzer as a Model Context Protocol server for AI assistants
2. **Model Training** - Fine-tuning large language models for Sanskrit grammar analysis and disambiguation

The MCP server provides immediate value while creating a data flywheel for continuous model improvement.

---

## Part 1: MCP Server Design

### 1.1 Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                    Sanskrit MCP Server                          │
│                    (HTTP/SSE Transport)                         │
│                    (Separate port from FastAPI)                 │
├─────────────────────────────────────────────────────────────────┤
│  Tools (12)                      │  Resources                   │
│  ─────────────                   │  ──────────                  │
│  • analyze_sentence              │  • /dhatus                   │
│  • split_sandhi                  │  • /grammar/sandhi-rules     │
│  • get_morphology                │  • /grammar/pratyayas        │
│  • transliterate                 │  • /grammar/sutras           │
│  • lookup_dhatu                  │                              │
│  • search_dhatu                  │                              │
│  • conjugate_verb                │                              │
│  • list_gana                     │                              │
│  • explain_parse                 │                              │
│  • identify_compound             │                              │
│  • get_pratyaya                  │                              │
│  • resolve_ambiguity             │                              │
├─────────────────────────────────────────────────────────────────┤
│                    Existing Sanskrit Analyzer                   │
│  ┌──────────┐  ┌────────────┐  ┌──────────┐  ┌──────────────┐  │
│  │ Ensemble │  │ TreeBuilder│  │ DhatuDB  │  │Disambiguation│  │
│  │ Analyzer │  │            │  │          │  │   Pipeline   │  │
│  └──────────┘  └────────────┘  └──────────┘  └──────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

### 1.2 Tool Specifications

All tools support a `verbosity` parameter: `minimal` | `standard` | `detailed`

#### Analysis Tools

| Tool | Parameters | Returns |
|------|------------|---------|
| `analyze_sentence` | `text: str`, `mode?: educational\|production\|academic`, `verbosity?` | Full parse tree with sandhi groups, words, meanings |
| `split_sandhi` | `text: str`, `verbosity?` | List of sandhi groups with split points and rules applied |
| `get_morphology` | `word: str`, `context?: str`, `verbosity?` | Morphological tags (case, gender, number, tense, etc.) |
| `transliterate` | `text: str`, `from_script: str`, `to_script: str` | Converted text |

#### Dhatu Tools

| Tool | Parameters | Returns |
|------|------------|---------|
| `lookup_dhatu` | `dhatu: str`, `include_conjugations?: bool`, `verbosity?` | DhatuEntry with meanings, gana, examples |
| `search_dhatu` | `query: str`, `limit?: int`, `verbosity?` | List of matching dhatus |
| `conjugate_verb` | `dhatu: str`, `lakara?: str`, `purusha?: str`, `vacana?: str` | Conjugation table or specific forms |
| `list_gana` | `gana: 1-10`, `limit?: int` | Dhatus in that verb class |

#### Grammar Tools

| Tool | Parameters | Returns |
|------|------------|---------|
| `explain_parse` | `text: str`, `parse_indices?: list[int]`, `verbosity?` | Comparison of parse interpretations |
| `identify_compound` | `word: str`, `verbosity?` | Compound type (tatpurusa, dvandva, etc.) with breakdown |
| `get_pratyaya` | `word: str`, `verbosity?` | Suffixes applied with grammatical function |
| `resolve_ambiguity` | `text: str`, `context?: str` | Disambiguated parse with reasoning |

### 1.3 Resource Definitions

#### `/dhatus` - Dhatu Database
```
/dhatus                     → Overview: count, gana distribution
/dhatus/gana/{1-10}         → List all dhatus in a gana
/dhatus/{dhatu}             → Full entry for specific dhatu
/dhatus/{dhatu}/conjugations → Complete conjugation tables
```

#### `/grammar/sandhi-rules` - Sandhi Reference
```
/grammar/sandhi-rules              → Index of sandhi categories
/grammar/sandhi-rules/vowel        → Vowel sandhi (ac-sandhi)
/grammar/sandhi-rules/consonant    → Consonant sandhi (hal-sandhi)
/grammar/sandhi-rules/visarga      → Visarga sandhi
```

#### `/grammar/pratyayas` - Suffix Reference
```
/grammar/pratyayas                 → Index of suffix types
/grammar/pratyayas/krt             → Primary suffixes (krt pratyayas)
/grammar/pratyayas/taddhita        → Secondary suffixes
/grammar/pratyayas/tin             → Verb endings (tin pratyayas)
/grammar/pratyayas/sup             → Noun endings (sup pratyayas)
```

#### `/grammar/sutras` - Paninian Reference
```
/grammar/sutras                    → Astadhyayi overview
/grammar/sutras/{adhyaya}/{pada}   → Sutras by chapter/section
/grammar/sutras/search?q={term}    → Search sutras by topic
```

### 1.4 Implementation Structure

```
sanskrit_analyzer/
├── mcp/
│   ├── __init__.py
│   ├── server.py           # MCP server setup, HTTP/SSE transport
│   ├── tools/
│   │   ├── __init__.py
│   │   ├── analysis.py     # analyze_sentence, split_sandhi, etc.
│   │   ├── dhatu.py        # lookup_dhatu, search_dhatu, etc.
│   │   └── grammar.py      # explain_parse, identify_compound, etc.
│   └── resources/
│       ├── __init__.py
│       ├── dhatus.py       # /dhatus resource provider
│       └── grammar.py      # /grammar/* resource providers
├── data/
│   ├── sandhi_rules.yaml   # Sandhi rule definitions
│   ├── pratyayas.yaml      # Suffix reference data
│   └── sutras.yaml         # Paninian sutra data
```

### 1.5 Deployment

- **Transport:** HTTP/SSE (remote access)
- **Port:** Separate from existing FastAPI (e.g., 8001)
- **Location:** Homelab deployment
- **Config:** Environment variables or `config.yaml`

---

## Part 2: Model Training Design

### 2.1 Training Goals

| Model | Purpose | Output Format |
|-------|---------|---------------|
| `sanskrit-grammar-70b` | Full parse, morphology, sandhi | Structured JSON (matching analyzer schema) |
| `sanskrit-disambig-70b` | Parse selection with reasoning | JSON with `selected` index + `reasoning` text |

### 2.2 Data Pipeline

```
┌──────────────┐    ┌─────────────────┐    ┌──────────────┐
│   Sanskrit   │    │   3-Engine      │    │   Filter     │
│   Corpora    │───▶│   Ensemble      │───▶│   High       │
│  (Ramayana,  │    │   Analyzer      │    │   Confidence │
│   Mahabharata)    │                 │    │   (>0.85)    │
└──────────────┘    └─────────────────┘    └──────────────┘
                                                  │
                    ┌─────────────────────────────┘
                    ▼
┌─────────────────────────────────────────────────────────┐
│                  Training Examples                       │
├─────────────────────────────────────────────────────────┤
│  Grammar Tasks (JSON output):                           │
│  {"input": "रामो वनं गच्छति",                           │
│   "output": {"sandhi_groups": [...], "words": [...]}}   │
├─────────────────────────────────────────────────────────┤
│  Disambiguation (with reasoning):                        │
│  {"parses": [...], "selected": 1,                       │
│   "reasoning": "Case agreement: रामः (nom) + गच्छति"}   │
└─────────────────────────────────────────────────────────┘
```

### 2.3 Source Corpora

**Phase 1 (Initial):**
- Ramayana
- Mahabharata
- Puranas
- Kavya literature

**Phase 2 (Expansion):**
- Vedic texts (Upanisads, Brahmanas)
- Technical sastras (grammar, philosophy)

### 2.4 Training Data Formats

#### Grammar Model (JSON Output)
```json
{
  "input": "Parse: रामो वनं गच्छति",
  "output": {
    "sandhi_groups": [
      {
        "surface_form": "रामो",
        "base_words": [{"lemma": "राम", "morphology": "noun-nom-sg-m"}]
      },
      {
        "surface_form": "वनं",
        "base_words": [{"lemma": "वन", "morphology": "noun-acc-sg-n"}]
      },
      {
        "surface_form": "गच्छति",
        "base_words": [{"lemma": "गम्", "morphology": "verb-3sg-pres-act", "dhatu": "√गम्"}]
      }
    ],
    "confidence": 0.95
  }
}
```

#### Disambiguation Model (Reasoning Format)
```json
{
  "input": {
    "text": "कृष्णं वन्दे",
    "parses": [
      {"interpretation": "I worship Krishna", "confidence": 0.7},
      {"interpretation": "Krishna worships", "confidence": 0.6}
    ],
    "context": "Devotional verse opening"
  },
  "output": {
    "selected": 0,
    "reasoning": "Rule 'verb_agreement' matched: वन्दे is first-person singular (uttama-purusha), requiring the speaker as subject. कृष्णम् is accusative (object). Parse 1 incorrectly treats कृष्ण as nominative subject.",
    "confidence": 0.87
  }
}
```

### 2.5 Reasoning Generation

Reasoning explanations generated from rule-based templates:

```python
REASONING_TEMPLATES = {
    "case_agreement": "Rule 'case_agreement' matched: {nominative} (nom) agrees with verb {verb}. {alternative} has {wrong_case} which cannot be the subject.",
    "verb_agreement": "Rule 'verb_agreement' matched: {verb} is {person}-person {number}, requiring {expected_subject}. {parse_issue}.",
    "sandhi_preference": "Rule 'sandhi_preference' matched: {preferred_split} follows standard {sandhi_type} sandhi rules. {alternative_split} would require irregular sandhi.",
    "semantic_coherence": "Rule 'semantic_coherence' matched: {selected_meaning} is contextually appropriate given {context}. {alternative_meaning} is semantically unlikely here."
}
```

### 2.6 Training Infrastructure

**Hardware:** Mac Ultra (Apple Silicon)

**Stack:**
- Framework: MLX (Apple-optimized)
- Technique: QLoRA (4-bit quantization + LoRA adapters)
- Base Models: Llama-3.1-70B or Qwen2-72B (quantized)

**Configuration:**
```yaml
training:
  lora_rank: 64
  lora_alpha: 128
  target_modules: [q_proj, k_proj, v_proj, o_proj]
  batch_size: 1
  gradient_accumulation_steps: 16
  learning_rate: 2e-4
  lr_scheduler: cosine
  epochs: 3-5

quantization:
  bits: 4
  double_quant: true
  quant_type: nf4
```

**Estimated Training Data:**
- Grammar model: ~50K examples
- Disambiguation model: ~10K examples

**Output:** LoRA adapter weights (~100-500MB per model)

---

## Part 3: Integration & Data Flywheel

### 3.1 System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    Complete System Architecture                  │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│   ┌─────────────┐         ┌─────────────────────────────────┐  │
│   │ AI Clients  │◀───────▶│      Sanskrit MCP Server        │  │
│   │ (Claude,    │  HTTP/  │  ┌─────────┐ ┌───────────────┐  │  │
│   │  GPT, etc)  │   SSE   │  │  Tools  │ │   Resources   │  │  │
│   └─────────────┘         │  └────┬────┘ └───────────────┘  │  │
│         │                 └───────┼─────────────────────────┘  │
│         │ User corrections       │                              │
│         ▼                        ▼                              │
│   ┌─────────────┐         ┌─────────────────────────────────┐  │
│   │  Feedback   │         │      Sanskrit Analyzer           │  │
│   │  Collector  │────────▶│  ┌─────────┐ ┌───────────────┐  │  │
│   └─────────────┘         │  │Ensemble │ │ Trained Models│  │  │
│         │                 │  │(Vidyut, │ │ (Grammar +    │  │  │
│         │                 │  │Dharma,  │ │ Disambig)     │  │  │
│         │                 │  │Heritage)│ │               │  │  │
│         │                 │  └─────────┘ └───────────────┘  │  │
│         │                 └─────────────────────────────────┘  │
│         │                                                       │
│         ▼                                                       │
│   ┌─────────────────────────────────────────────────────────┐  │
│   │              Training Data Repository                    │  │
│   │  • High-confidence synthetic examples                    │  │
│   │  • Human-corrected disambiguation                        │  │
│   │  • User feedback from MCP interactions                   │  │
│   └──────────────────────────┬──────────────────────────────┘  │
│                              │                                  │
│                              ▼  (Periodic retraining)           │
│                       ┌─────────────┐                          │
│                       │  Fine-tune  │                          │
│                       │  on Mac     │                          │
│                       │  Ultra      │                          │
│                       └─────────────┘                          │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### 3.2 Data Flywheel

1. **MCP server serves AI clients** - Tools provide Sanskrit analysis
2. **Users interact and correct** - `resolve_ambiguity` captures corrections
3. **Feedback feeds training repo** - Human corrections become gold-standard data
4. **Periodic retraining** - Models improve with new data
5. **Better models → better responses** - Improved accuracy attracts more usage
6. **More usage → more data** - Cycle continues

### 3.3 Feedback Collection Schema

```json
{
  "id": "uuid",
  "timestamp": "2026-02-02T12:00:00Z",
  "tool": "resolve_ambiguity",
  "input": {
    "text": "...",
    "parses": [...],
    "context": "..."
  },
  "model_output": {
    "selected": 1,
    "reasoning": "...",
    "confidence": 0.75
  },
  "user_correction": {
    "selected": 0,
    "feedback": "Parse 0 is correct because..."
  },
  "validated": false
}
```

---

## Implementation Phases

### Phase 1: MCP Server (Immediate)
1. Set up MCP server skeleton with HTTP/SSE transport
2. Implement core analysis tools (analyze_sentence, split_sandhi, etc.)
3. Implement dhatu tools wrapping existing DhatuDB
4. Add grammar tools
5. Create resource providers for dhatus and grammar references
6. Deploy to homelab on separate port
7. Test with Claude Desktop / Claude Code

### Phase 2: Training Data Generation
1. Acquire/prepare classical Sanskrit corpora (Ramayana, Mahabharata)
2. Run batch analysis through 3-engine ensemble
3. Filter high-confidence outputs (>0.85)
4. Convert to training format (JSON structured output)
5. Generate disambiguation examples with rule-based reasoning templates
6. Validate sample with manual review

### Phase 3: Model Training
1. Set up MLX training environment on Mac Ultra
2. Download and quantize base model (Llama-3.1-70B)
3. Configure QLoRA training
4. Train grammar model on ~50K examples
5. Train disambiguation model on ~10K examples
6. Evaluate on held-out test set
7. Integrate trained models into analyzer pipeline

### Phase 4: Feedback Loop
1. Add feedback collection to MCP server
2. Implement user correction storage
3. Build validation UI for reviewing corrections
4. Establish retraining schedule
5. Monitor model performance over time

---

## Open Questions for Implementation

1. **Sutra data source:** Where to obtain structured Paninian sutra data for `/grammar/sutras` resource?
2. **Corpus licensing:** Confirm licensing for Ramayana/Mahabharata digital texts
3. **MCP SDK version:** Which version of the MCP Python SDK to target?
4. **Model hosting:** Run fine-tuned models via MLX server or integrate directly?

---

## Success Metrics

| Metric | Target |
|--------|--------|
| MCP tool response latency | <500ms for simple lookups, <2s for full analysis |
| Grammar model accuracy | >90% agreement with ensemble on test set |
| Disambiguation model accuracy | >85% agreement with human annotations |
| Training data volume | 50K grammar + 10K disambiguation examples |
| Feedback collection rate | Track for data flywheel health |

---

*Design completed: 2026-02-02*
