# PRD: Streamlit UI for Sanskrit Analyzer

## Introduction

Create a Streamlit-based web UI for the Sanskrit Analyzer that provides an intuitive, folder-expansion style interface for exploring sentence parse trees. The UI connects to the existing FastAPI backend and supports multiple user modes (Educational, Research, Quick Lookup) with adaptive detail levels.

## Goals

- Provide a clean, minimal UI for analyzing Sanskrit text
- Display hierarchical parse trees with expandable folder-style navigation
- Support multiple analysis modes (Educational/Research/Quick)
- Enable comparison of ambiguous parse candidates with diff highlighting
- Persist query history in browser localStorage
- Show detailed error messages with troubleshooting guidance when API is unavailable

## User Stories

### US-001: Project Setup and API Client
**Description:** As a developer, I need the basic project structure and API client so that the UI can communicate with the FastAPI backend.

**Acceptance Criteria:**
- [ ] Create `ui/` directory with proper module structure
- [ ] Implement `api_client.py` with async HTTP client using `httpx`
- [ ] API client has methods: `analyze(text, mode)`, `health_check()`
- [ ] API URL configurable via `SANSKRIT_API_URL` environment variable (default: `http://localhost:8000`)
- [ ] Typecheck passes (`mypy`)
- [ ] Unit tests for API client with mocked responses

---

### US-002: Main App Layout and Header
**Description:** As a user, I want to see a clean app layout with a header and mode selector so I can choose my analysis mode.

**Acceptance Criteria:**
- [ ] Main entry point at `ui/app.py`
- [ ] Header displays app title "Sanskrit Analyzer"
- [ ] Mode dropdown selector in header (Educational / Research / Quick)
- [ ] Selected mode stored in session state
- [ ] Minimal/clean styling (white background, subtle borders)
- [ ] Typecheck passes
- [ ] Verify in browser manually

---

### US-003: Split Input Panel
**Description:** As a user, I want an input area with text box on the left and examples/history on the right so I can quickly enter or select text to analyze.

**Acceptance Criteria:**
- [ ] Left column (60%): Text input field + "Analyze" button
- [ ] Right column (40%): "Examples" section with 3-5 clickable Sanskrit sentences
- [ ] Right column: "History" section showing recent queries (from localStorage)
- [ ] Clicking an example or history item populates the text input
- [ ] Typecheck passes
- [ ] Unit tests for input panel component
- [ ] Verify in browser manually

---

### US-004: History Persistence with localStorage
**Description:** As a user, I want my query history to persist across browser sessions so I can revisit previous analyses.

**Acceptance Criteria:**
- [ ] Implement `state.py` with history management functions
- [ ] History stored in browser localStorage via `streamlit-javascript` or custom component
- [ ] Maximum 20 history entries (FIFO eviction)
- [ ] Each history entry stores: text, timestamp, mode
- [ ] Clear history button available
- [ ] Typecheck passes
- [ ] Unit tests for state management logic

---

### US-005: API Call and Loading State
**Description:** As a user, I want to see a loading indicator while analysis is in progress so I know the system is working.

**Acceptance Criteria:**
- [ ] Clicking "Analyze" shows spinner with "Analyzing..." message
- [ ] API call made to `POST /api/v1/analyze` with text and mode
- [ ] Successful response stored in session state
- [ ] Loading state prevents duplicate submissions
- [ ] Typecheck passes
- [ ] Integration test for analyze flow with mocked API

---

### US-006: Error Handling with Troubleshooting
**Description:** As a user, I want detailed error messages when something goes wrong so I can troubleshoot the issue.

**Acceptance Criteria:**
- [ ] Connection refused: "Cannot connect to API server. Ensure the backend is running at {url}"
- [ ] Timeout: "Request timed out. The server may be overloaded. Try again in a moment."
- [ ] 4xx errors: Display API error message from response
- [ ] 5xx errors: "Server error occurred. Please try again or check server logs."
- [ ] Error displayed in red alert box with icon
- [ ] Typecheck passes
- [ ] Unit tests for error handling scenarios

---

### US-007: Results Header Display
**Description:** As a user, I want to see a summary of my analysis results so I understand the overall output at a glance.

**Acceptance Criteria:**
- [ ] Results section appears after successful analysis
- [ ] Shows: original sentence, overall confidence percentage, script variants (Devanagari, IAST, SLP1)
- [ ] "Compare" button visible only when multiple parse candidates exist
- [ ] Number of parse candidates displayed
- [ ] Typecheck passes
- [ ] Verify in browser manually

---

### US-008: Parse Candidate List (Collapsed View)
**Description:** As a user, I want to see a ranked list of parse candidates so I can understand the different interpretations.

**Acceptance Criteria:**
- [ ] Parse candidates listed in order of confidence (highest first)
- [ ] Each candidate shows: rank, confidence percentage, brief word summary
- [ ] First (best) candidate marked as "Selected"
- [ ] Collapsed state shows `▸` arrow indicator
- [ ] Clicking a candidate expands it (shows `▼`)
- [ ] Typecheck passes
- [ ] Unit tests for parse list component

---

### US-009: Expandable Parse Tree (Folder View)
**Description:** As a user, I want to expand a parse candidate to see its hierarchical structure (SandhiGroups → BaseWords) so I can explore the grammatical breakdown.

**Acceptance Criteria:**
- [ ] Implement `parse_tree.py` component
- [ ] Expanded parse shows SandhiGroups with tree-line styling (`├─`, `└─`)
- [ ] Each SandhiGroup expandable to show BaseWords
- [ ] Visual indentation with CSS border-left for tree lines
- [ ] Collapse/expand state managed in session state
- [ ] Typecheck passes
- [ ] Unit tests for tree expansion logic
- [ ] Verify in browser manually

---

### US-010: Word Card (Minimal View)
**Description:** As a user, I want to see basic word information by default so I get a quick overview without clutter.

**Acceptance Criteria:**
- [ ] Implement `word_card.py` component
- [ ] Minimal view shows: lemma (with transliteration), POS, core morphology tags, primary meaning
- [ ] For verbs: show dhatu (√root) with meaning
- [ ] "[Show more...]" link at bottom of card
- [ ] Typecheck passes
- [ ] Unit tests for word card rendering

---

### US-011: Word Card (Expanded View)
**Description:** As a user, I want to see full word details when I click "Show more" so I can access scholarly information.

**Acceptance Criteria:**
- [ ] Expanded view adds: all script variants, all meanings, pratyayas, upasargas, confidence score, engine votes
- [ ] Card-style layout with sections (Morphology, Scripts, Meanings, Confidence)
- [ ] "[Show less]" link to collapse
- [ ] Typecheck passes
- [ ] Verify in browser manually

---

### US-012: Diff Comparison View
**Description:** As a user, I want to compare parse candidates side-by-side with differences highlighted so I can understand why interpretations differ.

**Acceptance Criteria:**
- [ ] Implement `diff_view.py` component
- [ ] "Compare" button opens comparison modal/section
- [ ] Side-by-side columns showing Parse 1 vs Parse 2
- [ ] Words that differ between parses highlighted with indicator
- [ ] Close button to return to normal view
- [ ] Typecheck passes
- [ ] Unit tests for diff logic
- [ ] Verify in browser manually

---

### US-013: Custom CSS Styling
**Description:** As a developer, I need custom CSS for tree-line styling and card layouts so the UI looks polished.

**Acceptance Criteria:**
- [ ] Implement `styles.py` with CSS injection via `st.markdown`
- [ ] Tree lines: `border-left` with proper indentation
- [ ] Card styling: subtle borders, consistent padding
- [ ] Responsive layout (works on tablet/desktop)
- [ ] No custom fonts (use Streamlit defaults)
- [ ] Verify in browser manually

---

### US-014: Integration Tests for Full Flow
**Description:** As a developer, I need integration tests that verify the full analysis flow works correctly.

**Acceptance Criteria:**
- [ ] Test: input text → API call → results displayed
- [ ] Test: mode selection affects API request
- [ ] Test: history updates after successful analysis
- [ ] Test: error states display correctly
- [ ] Tests use mocked API responses (no real backend required)
- [ ] All tests pass in CI

---

### US-015: Documentation and Run Instructions
**Description:** As a developer, I need documentation on how to run and test the UI.

**Acceptance Criteria:**
- [ ] Update README.md with Streamlit UI section
- [ ] Document: installation, environment variables, run command
- [ ] Document: how to run tests
- [ ] Add `ui/README.md` with component architecture overview

---

## Functional Requirements

- **FR-1:** UI must connect to FastAPI backend via HTTP (configurable URL)
- **FR-2:** Text input accepts any Sanskrit script (Devanagari, IAST, SLP1, ITRANS)
- **FR-3:** Mode selector offers three options: Educational, Research, Quick
- **FR-4:** Parse tree displays 4-level hierarchy: Sentence → Parse → SandhiGroup → Word
- **FR-5:** Tree nodes are expandable/collapsible with visual indicators (▸/▼)
- **FR-6:** Word details show minimal info by default, full info on expansion
- **FR-7:** Multiple parse candidates displayed in ranked list by confidence
- **FR-8:** Diff comparison highlights differences between two parse candidates
- **FR-9:** Query history persists in browser localStorage (max 20 entries)
- **FR-10:** Errors display with specific troubleshooting guidance based on error type

## Non-Goals (Out of Scope)

- User authentication or accounts
- Server-side history storage
- Offline mode / cached examples when API unavailable
- Mobile-optimized responsive design (tablet/desktop only)
- Dark mode theme support
- Keyboard shortcuts
- Export/download functionality for results
- WebSocket real-time updates

## Technical Considerations

### File Structure
```
sanskrit_analyzer/
├── ui/
│   ├── __init__.py
│   ├── app.py              # Main Streamlit entry point
│   ├── api_client.py       # HTTP client for FastAPI backend
│   ├── state.py            # Session state & localStorage management
│   ├── styles.py           # Custom CSS
│   ├── components/
│   │   ├── __init__.py
│   │   ├── input_panel.py  # Text input + examples/history
│   │   ├── results_header.py # Results summary display
│   │   ├── parse_tree.py   # Folder expansion tree view
│   │   ├── word_card.py    # Expandable word details
│   │   └── diff_view.py    # Parse comparison view
│   └── README.md           # Component documentation
├── tests/
│   └── ui/
│       ├── __init__.py
│       ├── test_api_client.py
│       ├── test_state.py
│       ├── test_components.py
│       └── test_integration.py
```

### Dependencies
```
streamlit>=1.28.0
streamlit-javascript>=0.1.5  # For localStorage access
httpx>=0.25.0  # Already in project
pytest>=7.0.0  # Already in project
pytest-asyncio>=0.21.0
```

### Environment Variables
| Variable | Default | Description |
|----------|---------|-------------|
| `SANSKRIT_API_URL` | `http://localhost:8000` | FastAPI backend URL |

### Run Commands
```bash
# Run the UI
streamlit run sanskrit_analyzer/ui/app.py

# Run tests
pytest tests/ui/ -v

# Run with coverage
pytest tests/ui/ --cov=sanskrit_analyzer/ui
```

## Success Metrics

- User can analyze a sentence and view results in under 3 clicks
- Tree expansion/collapse responds in <100ms
- All unit and integration tests pass
- Error messages provide actionable troubleshooting steps
- History persists correctly across browser refresh

## Open Questions

1. Should we add a "Copy to clipboard" button for results?
2. Should examples be hardcoded or fetched from the API?
3. Do we need a health check indicator in the UI header showing API status?
