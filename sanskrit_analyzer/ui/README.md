# Sanskrit Analyzer Streamlit UI

A web-based interface for analyzing Sanskrit text using a folder-expansion style tree view.

## Quick Start

```bash
# Run the UI
streamlit run sanskrit_analyzer/ui/app.py

# Run tests
pytest tests/ui/ -v
```

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `SANSKRIT_API_URL` | `http://localhost:8000` | FastAPI backend URL |

## Component Architecture

```
ui/
├── app.py              # Main Streamlit entry point
├── api_client.py       # HTTP client for FastAPI backend
├── state.py            # Session state management
├── styles.py           # Custom CSS injection
└── components/
    ├── input_panel.py      # Text input + examples + history
    ├── results_header.py   # Sentence display + confidence + scripts
    ├── word_card.py        # Expandable word details
    ├── parse_tree.py       # Folder-style parse tree
    └── diff_view.py        # Side-by-side parse comparison
```

## Features

- **Multiple Analysis Modes**: Educational, Research, Quick
- **Folder-Style Parse Tree**: Expandable hierarchy (Parse → SandhiGroup → Word)
- **Word Cards**: Minimal view by default, full details on expansion
- **Parse Comparison**: Side-by-side diff view for ambiguous sentences
- **Query History**: Recent queries persisted in session

## API Client

The `SanskritAPIClient` communicates with the FastAPI backend:

```python
from sanskrit_analyzer.ui.api_client import SanskritAPIClient

client = SanskritAPIClient()
result = await client.analyze("रामः गच्छति", mode="educational")

if result.success:
    print(result.data)
else:
    print(result.error.message)
```

## State Management

Session state is managed through the `state` module:

```python
from sanskrit_analyzer.ui.state import (
    add_to_history,
    get_history,
    toggle_parse_expanded,
    is_parse_expanded,
)

# Add to history
add_to_history("रामः गच्छति", "educational")

# Toggle UI expansion
toggle_parse_expanded("parse_1")
```
