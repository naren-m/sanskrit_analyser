# Sanskrit Analyzer Training Data Generation

Generate training data for fine-tuning language models on Sanskrit grammar analysis and disambiguation.

## Overview

This module provides tools to:
1. Load Sanskrit corpora from text or JSON files
2. Process text through the Sanskrit Analyzer
3. Convert output to training formats
4. Generate reasoning for disambiguation examples
5. Validate and analyze training data

## Installation

The training module is included with sanskrit-analyzer:

```bash
pip install sanskrit-analyzer
```

## CLI Usage

### Generate Grammar Training Data

```bash
sanskrit-train generate-grammar \
    --corpus sanskrit_analyzer/data/corpora/sample_ramayana.txt \
    --output training_data/grammar.jsonl \
    --min-confidence 0.85
```

### Generate Disambiguation Training Data

```bash
sanskrit-train generate-disambig \
    --corpus sanskrit_analyzer/data/corpora/sample_gita.txt \
    --output training_data/disambig.jsonl
```

### Validate Training Data

```bash
sanskrit-train validate --input training_data/grammar.jsonl -v
```

### Get Statistics

```bash
sanskrit-train stats --input training_data/grammar.jsonl
sanskrit-train stats --input training_data/grammar.jsonl --json
```

## Corpus Format

### Plain Text (.txt)

One verse/sentence per line. Lines starting with `#` are comments.

```
# Sample Ramayana verses
रामो वनं गच्छति
सीता रामं अनुगच्छति
```

### JSON Format

```json
{
  "corpus": "Ramayana",
  "verses": [
    {"text": "रामो वनं गच्छति", "chapter": "1"},
    {"text": "सीता रामं अनुगच्छति", "chapter": "1"}
  ]
}
```

## Output Formats

### Grammar Training (JSONL)

```json
{
  "input": "Parse: रामो वनं गच्छति",
  "output": {
    "sandhi_groups": [
      {
        "surface_form": "रामो",
        "base_words": [{"lemma": "राम", "morphology": "noun-nom-sg-m"}]
      }
    ],
    "confidence": 0.95
  },
  "metadata": {
    "corpus": "Ramayana",
    "chapter": "1",
    "verse": 1
  }
}
```

### Disambiguation Training (JSONL)

```json
{
  "input": {
    "text": "कृष्णं वन्दे",
    "parses": [
      {"interpretation": "I worship Krishna", "confidence": 0.7},
      {"interpretation": "Krishna worships", "confidence": 0.6}
    ],
    "context": "Devotional verse"
  },
  "output": {
    "selected": 0,
    "reasoning": "Rule 'verb_agreement' matched: वन्दे is first-person singular...",
    "confidence": 0.87
  }
}
```

## Python API

```python
from pathlib import Path
from sanskrit_analyzer.training.config import TrainingConfig
from sanskrit_analyzer.training.corpus_loader import CorpusLoader
from sanskrit_analyzer.training.data_generator import BatchAnalyzer

# Configure
config = TrainingConfig(min_confidence=0.85, max_examples=1000)

# Load corpus
corpus = CorpusLoader(Path("corpus.txt"), corpus_name="MyCorpus")

# Generate training data
analyzer = BatchAnalyzer(config)
count = await analyzer.generate_training_data(corpus, Path("output.jsonl"))
print(f"Generated {count} examples")
```

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `TRAIN_MIN_CONFIDENCE` | 0.85 | Minimum confidence threshold |
| `TRAIN_MAX_EXAMPLES` | 0 | Maximum examples (0=unlimited) |
| `TRAIN_OUTPUT_DIR` | training_data | Output directory |
| `TRAIN_BATCH_SIZE` | 100 | Batch size for processing |

## Testing

```bash
pytest tests/training/ -v
```
