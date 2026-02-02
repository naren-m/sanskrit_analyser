# Sanskrit Analyzer

Centralized Sanskrit sentence parser with 3-engine ensemble analysis.

## Features

- **4-level parse trees**: Sentence → Sandhi Groups → Base Words → Dhatus
- **3-engine ensemble**: Vidyut (Paninian), Dharmamitra ByT5 (Neural), Sanskrit Heritage (Lexicon)
- **Hybrid disambiguation**: Rules → LLM → Human override
- **Tiered caching**: Memory → Redis → SQLite corpus
- **Multiple interfaces**: Python library, REST API, Vue+Cytoscape UI

## Installation

```bash
pip install sanskrit-analyzer
```

With all optional dependencies:

```bash
pip install sanskrit-analyzer[all]
```

## Quick Start

```python
from sanskrit_analyzer import Analyzer, AnalysisMode

analyzer = Analyzer()
result = analyzer.analyze("रामो गच्छति", mode=AnalysisMode.EDUCATIONAL)

for sandhi_group in result.best_parse.sandhi_groups:
    print(f"{sandhi_group.surface_form}")
    for word in sandhi_group.base_words:
        print(f"  └─ {word.lemma}: {word.meanings[0]}")
```

## Development

```bash
# Clone and install
git clone https://github.com/narenmudivarthy/sanskrit-analyzer.git
cd sanskrit-analyzer
uv venv && source .venv/bin/activate
uv pip install -e ".[dev]"

# Run tests
pytest

# Type check
mypy sanskrit_analyzer
```

## License

MIT
