# संस्कृत विश्लेषक | Sanskrit Analyzer

Sanskrit text analysis library: Vidyut + Heritage ensemble parsing, a local sandhi-aware segmenter with dhātu identification, hierarchical parse trees, and interactive visualization.

![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)
![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)

## Features

- **Ensemble Analysis**: Combines Vidyut and Sanskrit Heritage engines; an optional local ByT5 engine (`[ml]` extra) can be added
- **Deep Read**: Offline sandhi-aware DP segmenter over the `vidyut.kosha` lexicon with per-word dhātu identification (`DeepRead`)
- **Prakriyā Engine**: Verse analyzer with chandas identification and sūtra traces (`sanskrit_analyzer.prakriya`)
- **4-Level Parse Tree**: Sentence → Sandhi Groups → Base Words → Dhātus
- **Multi-Script Support**: Devanagari, IAST, SLP1, and ITRANS
- **Hybrid Disambiguation**: Rules → LLM → Human review pipeline
- **Tiered Caching**: Memory → Redis → SQLite for optimal performance
- **REST API**: FastAPI-based API with OpenAPI documentation
- **Interactive UI**: Vue.js frontend with Cytoscape tree visualization

## Quick Start

### Installation

```bash
# Clone the repository
git clone https://github.com/yourusername/sanskrit_analyzer.git
cd sanskrit_analyzer

# Install with pip
pip install -e ".[dev]"

# Or install just the core library
pip install -e .
```

### Basic Usage

```python
import asyncio
from sanskrit_analyzer import Analyzer
from sanskrit_analyzer.config import Config

async def main():
    # Initialize analyzer
    analyzer = Analyzer(Config())

    # Analyze Sanskrit text
    result = await analyzer.analyze("रामः गच्छति")

    # Access the parse tree
    print(f"Confidence: {result.confidence.overall:.2%}")

    for parse in result.parse_forest:
        for sg in parse.sandhi_groups:
            for word in sg.base_words:
                print(f"  {word.lemma}: {word.morphology}")

asyncio.run(main())
```

### Running the API

```bash
# Start the API server
uvicorn sanskrit_analyzer.api.app:create_app --factory --host 0.0.0.0 --port 8000

# API documentation at http://localhost:8000/docs
```

### Running the UI

**Streamlit UI (Python-based):**
```bash
# Run the Streamlit UI
streamlit run sanskrit_analyzer/ui/app.py

# UI available at http://localhost:8501
# Set API URL via environment variable:
# SANSKRIT_API_URL=http://localhost:8000 streamlit run sanskrit_analyzer/ui/app.py
```

**Vue.js UI (JavaScript-based):**
```bash
cd ui
npm install
npm run dev

# UI available at http://localhost:5173
```

### Docker Compose

```bash
cd docker
docker-compose up

# API: http://localhost:8000
# UI: http://localhost:3000
```

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     Sanskrit Analyzer                        │
├─────────────────────────────────────────────────────────────┤
│  ┌─────────┐  ┌──────────────┐  ┌─────────────┐            │
│  │ Vidyut  │  │ Local ByT5   │  │  Heritage   │  Engines   │
│  │ (0.35)  │  │ (0.45, opt.) │  │   (0.25)    │            │
│  └────┬────┘  └──────┬───────┘  └──────┬──────┘            │
│       └──────────────┼─────────────────┘                    │
│                      ▼                                       │
│              ┌───────────────┐                              │
│              │   Ensemble    │  Weighted voting              │
│              │   Analyzer    │                              │
│              └───────┬───────┘                              │
│                      ▼                                       │
│              ┌───────────────┐                              │
│              │  Tree Builder │  4-level hierarchy           │
│              └───────┬───────┘                              │
│                      ▼                                       │
│              ┌───────────────┐                              │
│              │ Disambiguation│  Rules → LLM → Human         │
│              │   Pipeline    │                              │
│              └───────┬───────┘                              │
│                      ▼                                       │
│  ┌─────────┐  ┌──────────────┐  ┌─────────────┐            │
│  │ Memory  │→ │    Redis     │→ │   SQLite    │  Cache     │
│  │  LRU    │  │   (7 days)   │  │   Corpus    │            │
│  └─────────┘  └──────────────┘  └─────────────┘            │
└─────────────────────────────────────────────────────────────┘
```

## Configuration

Create a `config.yaml` file:

```yaml
# Keys are flat and match the dataclass fields in sanskrit_analyzer/config.py.
# Unknown keys are silently dropped, so nested "vidyut: {enabled: true}" style
# configs are NOT honoured.
engines:
  vidyut: true
  vidyut_weight: 0.35
  heritage: false               # HTML parser is a stub; needs a Heritage server
  heritage_weight: 0.25
  heritage_mode: local          # local | remote | fallback
  heritage_local_url: "http://localhost:8080"
  local_byt5: false             # needs the [ml] extra
  local_byt5_weight: 0.45
  local_byt5_model: "chronbmm/sanskrit5-multitask"
  local_byt5_device: auto       # auto | cpu | cuda | mps

cache:
  memory_enabled: true
  memory_max_size: 1000
  redis_enabled: false
  redis_url: "redis://localhost:6379/0"
  redis_ttl_days: 7
  sqlite_enabled: true
  sqlite_path: "~/.sanskrit_analyzer/corpus.db"

disambiguation:
  rules_enabled: true
  min_confidence_skip: 0.95
  llm_enabled: false
  llm_provider: ollama          # ollama | openai
  llm_model: "llama3.2"
  ollama_url: "http://localhost:11434"
  human_enabled: false
```

Environment variables override config file settings:
- `SANSKRIT_REDIS_URL`: Redis connection URL
- `SANSKRIT_SQLITE_PATH`: Path to the SQLite corpus database
- `SANSKRIT_LLM_PROVIDER`: "ollama" or "openai"
- `SANSKRIT_LLM_MODEL`: Model name for LLM disambiguation
- `SANSKRIT_OLLAMA_URL`, `SANSKRIT_OPENAI_API_KEY`, `SANSKRIT_LOG_LEVEL`, `SANSKRIT_LOG_FILE`

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/analyze` | Analyze Sanskrit text |
| GET | `/api/v1/analyze/{id}` | Get cached analysis |
| POST | `/api/v1/disambiguate` | Save disambiguation choice |
| GET | `/api/v1/dhatu/{dhatu}` | Lookup dhatu information |
| POST | `/api/v1/dhatu/search` | Search dhatus |
| GET | `/health` | Health check |
| GET | `/health/detailed` | Detailed health with component status |

### Example API Call

```bash
curl -X POST http://localhost:8000/api/v1/analyze \
  -H "Content-Type: application/json" \
  -d '{"text": "रामः गच्छति", "mode": "educational"}'
```

## Data Models

### AnalysisTree (Top Level)
```python
@dataclass
class AnalysisTree:
    sentence_id: str
    original_text: str
    normalized_slp1: str
    scripts: ScriptVariants
    parse_forest: list[ParseTree]
    confidence: ConfidenceMetrics
    mode: str
    needs_human_review: bool
```

### ParseTree (Parse Candidate)
```python
@dataclass
class ParseTree:
    parse_id: str
    confidence: float
    sandhi_groups: list[SandhiGroup]
    is_selected: bool
```

### BaseWord (Individual Word)
```python
@dataclass
class BaseWord:
    word_id: str
    lemma: str
    surface_form: str
    scripts: ScriptVariants
    morphology: MorphologicalTag
    meanings: list[str]
    dhatu: DhatuInfo | None
    confidence: float
```

## Development

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=sanskrit_analyzer

# Run specific test file
pytest tests/test_analyzer.py
```

### Type Checking

```bash
mypy sanskrit_analyzer
```

### Linting

```bash
ruff check sanskrit_analyzer
ruff format sanskrit_analyzer
```

## Project Structure

```
sanskrit_analyzer/
├── sanskrit_analyzer/
│   ├── __init__.py
│   ├── analyzer.py           # Main Analyzer class
│   ├── config.py             # Configuration management
│   ├── tree_builder.py       # Parse tree construction
│   ├── models/
│   │   ├── tree.py           # Data models (AnalysisTree, etc.)
│   │   ├── morphology.py     # Morphological tags
│   │   ├── dhatu.py          # Dhatu information
│   │   └── scripts.py        # Script variants
│   ├── engines/
│   │   ├── base.py           # Abstract engine base
│   │   ├── vidyut_engine.py  # Vidyut wrapper
│   │   ├── heritage_engine.py
│   │   ├── local_byt5_engine.py  # optional, [ml] extra
│   │   └── ensemble.py       # Ensemble voting
│   ├── dhatu/                # Local sandhi DP segmenter + dhātu identifier
│   ├── deep_read/            # DeepRead facade + kosha engine
│   ├── prakriya/             # Verse analyzer, chandas, sūtra traces
│   ├── cache/
│   │   ├── memory.py         # LRU cache
│   │   ├── redis_cache.py    # Redis layer
│   │   ├── sqlite_corpus.py  # SQLite storage
│   │   └── tiered.py         # Cache coordinator
│   ├── disambiguation/
│   │   ├── rules.py          # Rule-based disambiguation
│   │   ├── llm.py            # LLM disambiguation
│   │   └── pipeline.py       # Full pipeline
│   ├── data/
│   │   └── dhatu_db.py       # Dhatu database
│   ├── api/
│   │   ├── app.py            # FastAPI application
│   │   └── routes/
│   │       ├── analyze.py
│   │       ├── dhatu.py
│   │       └── health.py
│   └── utils/
│       ├── transliterate.py
│       └── normalize.py
├── ui/                        # Vue.js frontend
├── tests/                     # Test suite
├── examples/                  # Usage examples
├── docker/                    # Docker configuration
└── docs/                      # Documentation
```

## Examples

See the `examples/` directory for complete usage examples:

- `basic_usage.py` - Simple text analysis
- `batch_analysis.py` - Processing multiple texts with statistics
- `integrate_ramayanam.py` - Integration pattern for knowledge graphs

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Make your changes
4. Run tests (`pytest`)
5. Run type checking (`mypy sanskrit_analyzer`)
6. Commit your changes (`git commit -m 'Add amazing feature'`)
7. Push to the branch (`git push origin feature/amazing-feature`)
8. Open a Pull Request

## License

MIT License - see [LICENSE](LICENSE) for details.

## Acknowledgments

- [Vidyut](https://github.com/ambuda-org/vidyut) - Sanskrit NLP toolkit by Ambuda
- [Cologne Digital Sanskrit Dictionaries](https://www.sanskrit-lexicon.uni-koeln.de/) - vyutpatti source data
- [chronbmm/sanskrit5-multitask](https://huggingface.co/chronbmm/sanskrit5-multitask) - optional local ByT5 model
- [Sanskrit Heritage](https://sanskrit.inria.fr) - INRIA Sanskrit tools
- [Panini](https://en.wikipedia.org/wiki/P%C4%81%E1%B9%87ini) - For the grammar that makes this all possible

---

*श्रद्धावाँल्लभते ज्ञानम्* | *śraddhāvān labhate jñānam* | "The faithful one obtains knowledge"
# sanskrit_analyser
