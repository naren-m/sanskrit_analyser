# Sanskrit Analyzer Integration Design

**Date:** 2026-03-17
**Status:** Approved
**Branch:** `feature/sanskrit-analyzer-integration` (all 3 repos)

## Overview

Integrate `sanskrit_analyzer` as an embedded library dependency into both `ramayanam` and `yoga_sutras` projects, replacing all existing Vidyut and Dharmamitra code with a unified 3-engine ensemble parser.

## Goals

1. **Better Analysis Quality** — Leverage ensemble (Vidyut + Dharmamitra + Heritage) consensus for higher accuracy and confidence metrics
2. **Educational Features** — Enable interactive parse trees, disambiguation UI, derivation steps
3. **Code Consolidation** — Single NLP codebase to maintain, reduce duplication

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    sanskrit_analyzer (library)                   │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐             │
│  │   Vidyut    │  │ Dharmamitra │  │  Heritage   │  (Engines)  │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘             │
│         └────────────────┼────────────────┘                     │
│                    ┌─────┴─────┐                                │
│                    │ Ensemble  │  (Weighted voting)             │
│                    └─────┬─────┘                                │
│                    ┌─────┴─────┐                                │
│                    │ Analyzer  │  ← Public API                  │
│                    └───────────┘                                │
└─────────────────────────────────────────────────────────────────┘
                              │
            ┌─────────────────┴─────────────────┐
            │                                   │
            ▼                                   ▼
┌───────────────────────┐           ┌───────────────────────┐
│      ramayanam        │           │     yoga_sutras       │
│  ┌─────────────────┐  │           │  ┌─────────────────┐  │
│  │ SanskritAdapter │  │           │  │ SanskritAdapter │  │
│  └────────┬────────┘  │           │  └────────┬────────┘  │
│           │           │           │           │           │
│  ┌────────┴────────┐  │           │  ┌────────┴────────┐  │
│  │  Guru Service   │  │           │  │ Sandhi Service  │  │
│  │  Graph Builder  │  │           │  │ Dict Service    │  │
│  │  Search System  │  │           │  │ Morph Service   │  │
│  └─────────────────┘  │           │  └─────────────────┘  │
└───────────────────────┘           └───────────────────────┘
```

**Key Design Decisions:**
- `sanskrit_analyzer` remains standalone, no changes to its core
- Each consuming project gets a thin `SanskritAdapter` class
- Adapter translates project-specific calls to `Analyzer.analyze()`
- Existing services in each project call the adapter instead of raw Vidyut/Dharmamitra

## Prerequisites: API Extensions to sanskrit_analyzer

Before integration, the following methods must be added to the `Analyzer` class:

```python
# sanskrit_analyzer/analyzer.py - additions needed

async def lookup_dhatu(self, dhatu: str) -> DhatuInfo | None:
    """Lookup dhatu information by root form."""
    return self.tree_builder._lookup_dhatu(dhatu)

async def dictionary_lookup(self, word: str) -> list[dict]:
    """Multi-source dictionary lookup."""
    # Delegate to existing dictionary infrastructure
    ...
```

These extensions expose existing internal functionality as public API.

## Dependency Setup

### Branch Strategy

```
sanskrit_analyzer:  main → feature/sanskrit-analyzer-integration
ramayanam:          main → feature/sanskrit-analyzer-integration
yoga_sutras:        main → feature/sanskrit-analyzer-integration
```

### Dependency Configuration

**Ramayanam** (`pyproject.toml` or `requirements.txt`):
```toml
[project.dependencies]
sanskrit-analyzer = { git = "file:///Users/narenmudivarthy/Projects/sanskrit_analyzer", branch = "feature/sanskrit-analyzer-integration" }
```

**Yoga Sutras** (`backend/requirements.txt`):
```
sanskrit-analyzer @ git+file:///Users/narenmudivarthy/Projects/sanskrit_analyzer@feature/sanskrit-analyzer-integration
```

**Production/CI** (later):
```toml
sanskrit-analyzer = { git = "ssh://git@github.com/narenmudivarthy/sanskrit_analyzer.git", branch = "main" }
```

## Adapter Layer Design

### Ramayanam Adapter

**File:** `api/services/sanskrit_adapter.py`

```python
from sanskrit_analyzer import Analyzer, Config, AnalysisMode
from sanskrit_analyzer.models import AnalysisTree, BaseWord, DhatuInfo
from sanskrit_analyzer.models import PartOfSpeech
import asyncio
import logging

logger = logging.getLogger(__name__)

class SanskritAdapter:
    """Unified Sanskrit analysis for Ramayanam."""

    def __init__(self):
        self._analyzer = None

    @property
    def analyzer(self) -> Analyzer:
        """Lazy initialization - expensive to create."""
        if self._analyzer is None:
            try:
                self._analyzer = Analyzer(Config())
            except Exception as e:
                logger.error(f"Failed to initialize Analyzer: {e}")
                raise
        return self._analyzer

    async def analyze_sloka(self, text: str, mode: AnalysisMode = AnalysisMode.PRODUCTION) -> AnalysisTree:
        """Analyze a sloka with full ensemble parsing."""
        return await self.analyzer.analyze(text, mode=mode)

    def analyze_sloka_sync(self, text: str, mode: AnalysisMode = AnalysisMode.PRODUCTION) -> AnalysisTree:
        """Sync wrapper for contexts that can't use async (Flask without async support)."""
        return asyncio.run(self.analyze_sloka(text, mode=mode))

    async def extract_entities_for_graph(self, text: str) -> list[dict]:
        """Extract entities suitable for Neo4j ingestion.

        Entities are identified by POS tag (proper nouns, etc.) rather than
        a dedicated is_entity flag.
        """
        result = await self.analyzer.analyze(text, mode=AnalysisMode.ACADEMIC)
        entities = []
        # Entity-like POS tags (nouns are potential entities)
        entity_pos = {PartOfSpeech.NOUN}
        for parse in result.parse_forest:
            for sg in parse.sandhi_groups:
                for word in sg.base_words:
                    if word.morphology and word.morphology.pos in entity_pos:
                        entities.append({
                            'lemma': word.lemma,
                            'pos': word.morphology.pos.value if word.morphology.pos else None,
                            'morphology': word.morphology.to_dict() if hasattr(word.morphology, 'to_dict') else {}
                        })
        return entities

    async def get_morphology(self, word: str) -> dict:
        """Get morphological analysis for dictionary panel."""
        result = await self.analyzer.analyze(word, mode=AnalysisMode.EDUCATIONAL)
        if result.parse_forest and result.parse_forest[0].sandhi_groups:
            first_word = result.parse_forest[0].sandhi_groups[0].base_words[0]
            if hasattr(first_word.morphology, 'to_dict'):
                return first_word.morphology.to_dict()
        return {}

    async def lookup_dhatu(self, dhatu: str) -> DhatuInfo | None:
        """Dhatu lookup for verb root analysis."""
        return await self.analyzer.lookup_dhatu(dhatu)
```

### Yoga Sutras Adapter

**File:** `backend/app/services/sanskrit_adapter.py`

```python
from sanskrit_analyzer import Analyzer, Config, AnalysisMode
from sanskrit_analyzer.models import AnalysisTree, SandhiGroup
import asyncio
import logging

logger = logging.getLogger(__name__)

class SanskritAdapter:
    """Unified Sanskrit analysis for Yoga Sutras."""

    def __init__(self):
        self._analyzer = None

    @property
    def analyzer(self) -> Analyzer:
        """Lazy initialization - expensive to create."""
        if self._analyzer is None:
            try:
                self._analyzer = Analyzer(Config())
            except Exception as e:
                logger.error(f"Failed to initialize Analyzer: {e}")
                raise
        return self._analyzer

    async def split_sandhi(self, compound: str) -> list[SandhiGroup]:
        """Split compound word with sandhi analysis."""
        result = await self.analyzer.analyze(compound, mode=AnalysisMode.EDUCATIONAL)
        return result.parse_forest[0].sandhi_groups if result.parse_forest else []

    def split_sandhi_sync(self, compound: str) -> list[SandhiGroup]:
        """Sync wrapper for Flask routes without async support."""
        return asyncio.run(self.split_sandhi(compound))

    async def analyze_word(self, word: str) -> dict:
        """Full word analysis for ClickableWord component."""
        result = await self.analyzer.analyze(word, mode=AnalysisMode.EDUCATIONAL)
        if not result.parse_forest:
            return {'word': word, 'analysis': None}

        first_parse = result.parse_forest[0]
        return {
            'word': word,
            'confidence': result.confidence.overall,
            'sandhi_groups': [
                sg.to_dict() if hasattr(sg, 'to_dict') else {'words': [w.lemma for w in sg.base_words]}
                for sg in first_parse.sandhi_groups
            ]
        }

    def analyze_word_sync(self, word: str) -> dict:
        """Sync wrapper for Flask routes without async support."""
        return asyncio.run(self.analyze_word(word))

    async def dictionary_lookup(self, word: str) -> list[dict]:
        """Multi-source dictionary lookup."""
        return await self.analyzer.dictionary_lookup(word)

    def dictionary_lookup_sync(self, word: str) -> list[dict]:
        """Sync wrapper for Flask routes without async support."""
        return asyncio.run(self.dictionary_lookup(word))
```

## Code Removal

### Files to Delete from Ramayanam

```
api/services/
├── dharmamitra_service.py      # DELETE - replaced by SanskritAdapter
├── sandhi_service.py           # DELETE - replaced by SanskritAdapter
└── morphology_service.py       # DELETE - replaced by SanskritAdapter

# Note: Verify these files exist before deletion during implementation
```

### Files to Delete from Yoga Sutras

```
backend/app/services/
├── sandhi_service.py           # DELETE - replaced by SanskritAdapter
├── dictionary_service.py       # DELETE - replaced by SanskritAdapter
├── morphology_service.py       # DELETE - replaced by SanskritAdapter
└── dharmamitra_service.py      # DELETE - replaced by SanskritAdapter

data/
└── vidyut-data/                # DELETE (entire directory) - now bundled in sanskrit_analyzer

# Note: Verify these files exist before deletion during implementation
```

### Dependencies to Remove

**Ramayanam:**
```diff
- vidyut>=0.4.0
- transformers>=4.35
- torch
+ sanskrit-analyzer @ git+file:///...
```

**Yoga Sutras:**
```diff
- vidyut>=0.4.0
- indic-transliteration>=2.3.0
- dharmamitra
+ sanskrit-analyzer @ git+file:///...
```

## Service Rewiring

### Ramayanam Controller Updates

**Before:**
```python
# api/controllers/morphology_controller.py
from services.dharmamitra_service import DharmamitraService

@morphology_bp.route('/analyze', methods=['POST'])
def analyze():
    service = DharmamitraService()
    result = service.analyze(request.json['text'])
    return jsonify(result)
```

**After (sync version for Flask compatibility):**
```python
# api/controllers/morphology_controller.py
from services.sanskrit_adapter import SanskritAdapter
from sanskrit_analyzer import AnalysisMode

adapter = SanskritAdapter()

@morphology_bp.route('/analyze', methods=['POST'])
def analyze():
    result = adapter.analyze_sloka_sync(request.json['text'], mode=AnalysisMode.EDUCATIONAL)
    return jsonify(result.to_dict() if hasattr(result, 'to_dict') else {})
```

### Yoga Sutras Route Updates

**Before:**
```python
# backend/app/routes/api.py
from services.sandhi_service import SandhiService

@api_bp.route('/split/<compound>')
def split_compound(compound):
    service = SandhiService()
    return jsonify(service.split(compound))
```

**After (sync version for Flask compatibility):**
```python
# backend/app/routes/api.py
from services.sanskrit_adapter import SanskritAdapter

adapter = SanskritAdapter()

@api_bp.route('/split/<compound>')
def split_compound(compound):
    groups = adapter.split_sandhi_sync(compound)
    return jsonify([
        g.to_dict() if hasattr(g, 'to_dict') else {'words': [w.lemma for w in g.base_words]}
        for g in groups
    ])
```

## Error Handling

```python
from sanskrit_analyzer import Analyzer, Config, AnalysisMode
from sanskrit_analyzer.models import AnalysisTree
import asyncio
import logging

logger = logging.getLogger(__name__)

class SanskritAdapter:
    async def analyze_sloka(self, text: str, mode: AnalysisMode = AnalysisMode.PRODUCTION) -> AnalysisTree | None:
        if not text or not text.strip():
            logger.debug("Empty text provided, returning None")
            return None
        try:
            return await self.analyzer.analyze(text, mode=mode)
        except ValueError as e:
            logger.warning(f"Invalid input for '{text[:50]}...': {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error analyzing text: {e}")
            raise

    async def analyze_with_fallback(self, text: str) -> AnalysisTree | None:
        """Try production mode, fall back to academic if low confidence."""
        result = await self.analyze_sloka(text, mode=AnalysisMode.PRODUCTION)
        if result is None or result.confidence.overall < 0.3:
            logger.info(f"Low confidence ({result.confidence.overall if result else 'None'}), retrying with ACADEMIC mode")
            result = await self.analyze_sloka(text, mode=AnalysisMode.ACADEMIC)
        return result
```

### Edge Cases

| Case | Handling |
|------|----------|
| Empty text | Return None immediately, don't call analyzer |
| Non-Sanskrit text | Analyzer returns low confidence, adapter logs warning |
| Network timeout (Redis cache) | Graceful degradation, use memory cache only |
| Model loading failure | Lazy init with logging, surface error to health check |
| Very long text (>10K chars) | Chunk into sentences, analyze separately |
| Mixed scripts (Devanagari + IAST) | Normalize to single script before analysis |

### Health Check Integration

```python
# api/routes/health.py
from services.sanskrit_adapter import SanskritAdapter
from sanskrit_analyzer import AnalysisMode
import asyncio

adapter = SanskritAdapter()

@health_bp.route('/health/detailed')
def detailed_health():
    checks = {
        'database': check_db(),
        'redis': check_redis(),
        'neo4j': check_neo4j(),
        'sanskrit_analyzer': check_sanskrit_analyzer()
    }
    return jsonify(checks)

def check_sanskrit_analyzer() -> dict:
    try:
        result = adapter.analyze_sloka_sync("रामः", mode=AnalysisMode.PRODUCTION)
        return {'status': 'healthy', 'confidence': result.confidence.overall if result else 0}
    except Exception as e:
        return {'status': 'unhealthy', 'error': str(e)}
```

## Testing Strategy

### New Test Files

**Ramayanam:** `tests/test_sanskrit_adapter.py`
**Yoga Sutras:** `backend/tests/test_sanskrit_adapter.py`

```python
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from services.sanskrit_adapter import SanskritAdapter
from sanskrit_analyzer import AnalysisMode

@pytest.fixture
def adapter():
    return SanskritAdapter()

def test_analyze_sloka_sync_returns_tree(adapter):
    """Test sync wrapper works correctly."""
    result = adapter.analyze_sloka_sync("रामः गच्छति")
    assert result is not None
    assert result.confidence.overall > 0.0

def test_empty_text_returns_none(adapter):
    """Test empty input handling."""
    result = adapter.analyze_sloka_sync("")
    assert result is None

@pytest.mark.asyncio
async def test_analyze_sloka_returns_tree(adapter):
    result = await adapter.analyze_sloka("रामः गच्छति")
    assert result.confidence.overall > 0.5
    assert len(result.parse_forest) > 0

@pytest.mark.asyncio
async def test_split_sandhi_decomposes_compound(adapter):
    groups = await adapter.split_sandhi("योगश्चित्तवृत्तिनिरोधः")
    assert len(groups) >= 1
```

### Mock Strategy

```python
def create_mock_analysis_tree():
    """Factory for mock AnalysisTree objects."""
    mock = MagicMock()
    mock.confidence.overall = 0.85
    mock.parse_forest = []
    mock.to_dict.return_value = {'confidence': 0.85, 'parses': []}
    return mock

@patch('services.sanskrit_adapter.SanskritAdapter.analyze_sloka_sync')
def test_morphology_endpoint(mock_analyze, client):
    mock_analyze.return_value = create_mock_analysis_tree()
    response = client.post('/api/morphology/analyze', json={'text': 'test'})
    assert response.status_code == 200
```

### Validation Checklist

- [ ] All 380 tests pass in `sanskrit_analyzer`
- [ ] Ramayanam tests pass with adapter
- [ ] Yoga Sutras tests pass with adapter
- [ ] E2E tests verify UI still works (word clicks, dictionary panels)

## Implementation Sequence

### Phase 1: Branch Setup

```bash
# sanskrit_analyzer
cd ~/Projects/sanskrit_analyzer
git checkout -b feature/sanskrit-analyzer-integration

# ramayanam
cd ~/Projects/ramayanam
git checkout -b feature/sanskrit-analyzer-integration

# yoga_sutras
cd ~/Projects/yoga_sutras
git checkout -b feature/sanskrit-analyzer-integration
```

### Phase 2: Sanskrit Analyzer Prep

1. Add `lookup_dhatu()` and `dictionary_lookup()` methods to `Analyzer` class
2. Ensure package is installable via git URL
3. Verify `pyproject.toml` has correct entry points
4. Run full test suite (380 tests)
5. Commit changes to feature branch

### Phase 3: Ramayanam Integration

1. Add git dependency to `requirements.txt`
2. Create `SanskritAdapter` class
3. Rewire controllers (use sync wrappers):
   - `morphology_controller.py`
   - `dhatu_controller.py`
   - `dictionary_controller.py`
4. Update `guru_service.py` to use richer parse data
5. Delete old service files (verify existence first)
6. Update tests
7. Run full test suite
8. Manual E2E verification

### Phase 4: Yoga Sutras Integration

1. Add git dependency to `backend/requirements.txt`
2. Create `SanskritAdapter` class
3. Rewire routes (use sync wrappers):
   - `/api/split/<compound>`
   - `/api/dictionary/<word>`
   - `/api/morphology/<word>`
4. Delete old service files (verify existence first)
5. Remove `vidyut-data/` directory
6. Update tests
7. Run full test suite
8. Manual E2E verification

### Phase 5: Cleanup & Documentation

1. Update README in each project
2. Update Docker files (remove vidyut-data volume mounts)
3. Update CI/CD pipelines for git dependency
4. Final cross-project integration test

## File Change Summary

| Project | Files Added | Files Modified | Files Deleted |
|---------|-------------|----------------|---------------|
| sanskrit_analyzer | 0 | 2-3 (analyzer.py, __init__.py) | 0 |
| ramayanam | 1 | 8-10 | 3-4 |
| yoga_sutras | 1 | 6-8 | 4-5 |

## Success Criteria

- [ ] All 3 repos have feature branches
- [ ] `sanskrit_analyzer` has new public API methods (`lookup_dhatu`, `dictionary_lookup`)
- [ ] `sanskrit_analyzer` installable via git URL
- [ ] Ramayanam tests pass (existing + new adapter tests)
- [ ] Yoga Sutras tests pass (existing + new adapter tests)
- [ ] E2E: Word clicks work, dictionary panels work, Guru Q&A works
- [ ] No duplicate Vidyut/Dharmamitra code remains
