# PRD: Sanskrit MCP Server (Phase 1)

## Introduction

Expose the Sanskrit Analyzer as a Model Context Protocol (MCP) server, enabling AI assistants like Claude to understand and analyze Sanskrit text in real-time. The server provides 12 tools for analysis, dhatu lookup, and grammar operations, plus 4 resource categories for browsing reference data.

This is Phase 1 of the larger Sanskrit AI initiative. The MCP server provides immediate value and establishes the foundation for the data flywheel (feedback collection for model training in later phases).

## Goals

- Enable AI assistants to call Sanskrit analysis functions via MCP protocol
- Expose 12 fine-grained tools covering analysis, dhatu, and grammar operations
- Provide browsable resources for dhatus, sandhi rules, pratyayas, and sutras
- Support configurable verbosity (minimal/standard/detailed) for all tools
- Deploy on homelab with HTTP/SSE transport on a separate port from existing FastAPI
- Achieve <500ms response time for simple lookups, <2s for full analysis

## User Stories

---

### US-001: Create MCP module structure
**Description:** As a developer, I need the basic module structure for MCP server code so that I have a place to add tools and resources.

**Acceptance Criteria:**
- [ ] Create `sanskrit_analyzer/mcp/__init__.py`
- [ ] Create `sanskrit_analyzer/mcp/server.py` (empty placeholder)
- [ ] Create `sanskrit_analyzer/mcp/tools/__init__.py`
- [ ] Create `sanskrit_analyzer/mcp/tools/analysis.py` (empty placeholder)
- [ ] Create `sanskrit_analyzer/mcp/tools/dhatu.py` (empty placeholder)
- [ ] Create `sanskrit_analyzer/mcp/tools/grammar.py` (empty placeholder)
- [ ] Create `sanskrit_analyzer/mcp/resources/__init__.py`
- [ ] Create `sanskrit_analyzer/mcp/resources/dhatus.py` (empty placeholder)
- [ ] Create `sanskrit_analyzer/mcp/resources/grammar.py` (empty placeholder)
- [ ] Typecheck passes

---

### US-002: Set up MCP server with HTTP/SSE transport
**Description:** As a developer, I need the MCP server skeleton with HTTP/SSE transport so AI clients can connect remotely.

**Acceptance Criteria:**
- [ ] Install `mcp` package and add to pyproject.toml dependencies
- [ ] Implement `create_server()` function in `server.py` that returns MCP Server instance
- [ ] Configure HTTP/SSE transport (not stdio)
- [ ] Server listens on configurable port (default 8001)
- [ ] Server can be started with `python -m sanskrit_analyzer.mcp.server`
- [ ] Typecheck passes

---

### US-003: Add MCP server configuration
**Description:** As a developer, I need server configuration options so deployment can be customized.

**Acceptance Criteria:**
- [ ] Add `MCPServerConfig` dataclass with: host, port, log_level
- [ ] Support configuration via environment variables: `MCP_HOST`, `MCP_PORT`, `MCP_LOG_LEVEL`
- [ ] Support configuration via existing `config.yaml` under new `mcp:` section
- [ ] Environment variables override config file values
- [ ] Typecheck passes

---

### US-004: Implement analyze_sentence tool
**Description:** As an AI assistant, I want to analyze a Sanskrit sentence so I can provide full morphological breakdown to users.

**Acceptance Criteria:**
- [ ] Register `analyze_sentence` tool with MCP server
- [ ] Accept parameters: `text: str`, `mode?: str` (educational|production|academic), `verbosity?: str`
- [ ] Call existing `Analyzer.analyze()` method
- [ ] Return JSON with sandhi_groups, words, meanings, confidence
- [ ] Handle errors gracefully with descriptive messages
- [ ] Typecheck passes

---

### US-005: Implement split_sandhi tool
**Description:** As an AI assistant, I want to split sandhi in Sanskrit text so I can show word boundaries without full analysis.

**Acceptance Criteria:**
- [ ] Register `split_sandhi` tool with MCP server
- [ ] Accept parameters: `text: str`, `verbosity?: str`
- [ ] Return list of sandhi groups with split points
- [ ] Include sandhi rule applied (sutra reference) when available
- [ ] Lighter weight than full analyze (skip disambiguation if possible)
- [ ] Typecheck passes

---

### US-006: Implement get_morphology tool
**Description:** As an AI assistant, I want to get morphological tags for a word so I can explain its grammatical function.

**Acceptance Criteria:**
- [ ] Register `get_morphology` tool with MCP server
- [ ] Accept parameters: `word: str`, `context?: str`, `verbosity?: str`
- [ ] Return morphological tags: case, gender, number, person, tense, mood, voice
- [ ] Support both Devanagari and IAST input
- [ ] Typecheck passes

---

### US-007: Implement transliterate tool
**Description:** As an AI assistant, I want to convert text between scripts so I can present Sanskrit in the user's preferred format.

**Acceptance Criteria:**
- [ ] Register `transliterate` tool with MCP server
- [ ] Accept parameters: `text: str`, `from_script: str`, `to_script: str`
- [ ] Support scripts: devanagari, iast, slp1, itrans
- [ ] Use existing `ScriptVariants` utilities
- [ ] Return converted text string
- [ ] Typecheck passes

---

### US-008: Implement lookup_dhatu tool
**Description:** As an AI assistant, I want to look up a dhatu by its root so I can explain verb meanings and forms.

**Acceptance Criteria:**
- [ ] Register `lookup_dhatu` tool with MCP server
- [ ] Accept parameters: `dhatu: str`, `include_conjugations?: bool`, `verbosity?: str`
- [ ] Call existing `DhatuDB.lookup_by_dhatu()` method
- [ ] Return DhatuEntry JSON with meanings, gana, pada, examples
- [ ] Optionally include full conjugation tables
- [ ] Typecheck passes

---

### US-009: Implement search_dhatu tool
**Description:** As an AI assistant, I want to search dhatus by meaning or pattern so I can find roots when users ask "what's the verb for X".

**Acceptance Criteria:**
- [ ] Register `search_dhatu` tool with MCP server
- [ ] Accept parameters: `query: str`, `limit?: int` (default 10), `verbosity?: str`
- [ ] Call existing `DhatuDB.search()` method
- [ ] Return list of matching DhatuEntry JSON objects
- [ ] Typecheck passes

---

### US-010: Implement conjugate_verb tool
**Description:** As an AI assistant, I want to get conjugation forms for a dhatu so I can show users how verbs inflect.

**Acceptance Criteria:**
- [ ] Register `conjugate_verb` tool with MCP server
- [ ] Accept parameters: `dhatu: str`, `lakara?: str`, `purusha?: str`, `vacana?: str`
- [ ] Call existing `DhatuDB.get_conjugation()` method
- [ ] Return conjugation table or filtered forms based on parameters
- [ ] Include both Devanagari and IAST forms
- [ ] Typecheck passes

---

### US-011: Implement list_gana tool
**Description:** As an AI assistant, I want to list dhatus by verb class (gana) so I can explain gana patterns to users.

**Acceptance Criteria:**
- [ ] Register `list_gana` tool with MCP server
- [ ] Accept parameters: `gana: int` (1-10), `limit?: int` (default 20)
- [ ] Call existing `DhatuDB.get_by_gana()` method
- [ ] Return list of DhatuEntry JSON objects in that gana
- [ ] Validate gana is 1-10, return error otherwise
- [ ] Typecheck passes

---

### US-012: Implement explain_parse tool
**Description:** As an AI assistant, I want to compare multiple parse interpretations so I can explain ambiguity to users.

**Acceptance Criteria:**
- [ ] Register `explain_parse` tool with MCP server
- [ ] Accept parameters: `text: str`, `parse_indices?: list[int]`, `verbosity?: str`
- [ ] Run analysis and return multiple parses from parse_forest
- [ ] If parse_indices provided, return only those parses
- [ ] Include confidence scores and engine votes for comparison
- [ ] Typecheck passes

---

### US-013: Implement identify_compound tool
**Description:** As an AI assistant, I want to identify compound types (samasa) so I can explain Sanskrit compound formation.

**Acceptance Criteria:**
- [ ] Register `identify_compound` tool with MCP server
- [ ] Accept parameters: `word: str`, `verbosity?: str`
- [ ] Detect compound type: tatpurusha, dvandva, bahuvrihi, avyayibhava, karmadharaya, dvigu
- [ ] Return compound type and component breakdown
- [ ] Use existing `CompoundType` enum
- [ ] Typecheck passes

---

### US-014: Implement get_pratyaya tool
**Description:** As an AI assistant, I want to identify suffixes applied to a word so I can explain word formation.

**Acceptance Criteria:**
- [ ] Register `get_pratyaya` tool with MCP server
- [ ] Accept parameters: `word: str`, `verbosity?: str`
- [ ] Analyze word and return list of pratyayas (suffixes) applied
- [ ] Include pratyaya type (krt, taddhita, tin, sup) and grammatical function
- [ ] Use existing `Pratyaya` model
- [ ] Typecheck passes

---

### US-015: Implement resolve_ambiguity tool
**Description:** As an AI assistant, I want to resolve ambiguous parses so I can give users the most likely interpretation.

**Acceptance Criteria:**
- [ ] Register `resolve_ambiguity` tool with MCP server
- [ ] Accept parameters: `text: str`, `context?: str`
- [ ] Run full disambiguation pipeline (rules → LLM if enabled)
- [ ] Return selected parse index, confidence, and reasoning
- [ ] Include all parse candidates for reference
- [ ] Typecheck passes

---

### US-016: Add verbosity parameter handling
**Description:** As a developer, I need consistent verbosity handling across all tools so AI can control response detail level.

**Acceptance Criteria:**
- [ ] Create `Verbosity` enum: minimal, standard, detailed
- [ ] Create `format_response(data, verbosity)` helper function
- [ ] Minimal: essential data only (lemma, morphology codes)
- [ ] Standard: data with common fields expanded (default)
- [ ] Detailed: full data with explanatory text
- [ ] Apply to all tools that accept verbosity parameter
- [ ] Typecheck passes

---

### US-017: Create dhatus resource provider
**Description:** As an AI assistant, I want to browse the dhatu database as a resource so I can explore available roots.

**Acceptance Criteria:**
- [ ] Register `/dhatus` resource with MCP server
- [ ] `/dhatus` returns overview: total count, gana distribution
- [ ] `/dhatus/gana/{n}` returns dhatus in gana n (1-10)
- [ ] `/dhatus/{dhatu}` returns full entry for specific dhatu
- [ ] `/dhatus/{dhatu}/conjugations` returns conjugation tables
- [ ] Typecheck passes

---

### US-018: Create sandhi-rules resource provider
**Description:** As an AI assistant, I want to browse sandhi rules as a resource so I can cite specific rules when explaining.

**Acceptance Criteria:**
- [ ] Register `/grammar/sandhi-rules` resource with MCP server
- [ ] `/grammar/sandhi-rules` returns index of sandhi categories
- [ ] `/grammar/sandhi-rules/vowel` returns vowel sandhi rules (ac-sandhi)
- [ ] `/grammar/sandhi-rules/consonant` returns consonant sandhi rules (hal-sandhi)
- [ ] `/grammar/sandhi-rules/visarga` returns visarga sandhi rules
- [ ] Load rules from `data/sandhi_rules.yaml`
- [ ] Typecheck passes

---

### US-019: Create pratyayas resource provider
**Description:** As an AI assistant, I want to browse suffix reference as a resource so I can cite specific pratyayas.

**Acceptance Criteria:**
- [ ] Register `/grammar/pratyayas` resource with MCP server
- [ ] `/grammar/pratyayas` returns index of suffix types
- [ ] `/grammar/pratyayas/krt` returns primary suffixes (krt pratyayas)
- [ ] `/grammar/pratyayas/taddhita` returns secondary suffixes
- [ ] `/grammar/pratyayas/tin` returns verb endings
- [ ] `/grammar/pratyayas/sup` returns noun endings
- [ ] Load data from `data/pratyayas.yaml`
- [ ] Typecheck passes

---

### US-020: Create sutras resource provider
**Description:** As an AI assistant, I want to browse Paninian sutras as a resource so I can cite grammatical rules authoritatively.

**Acceptance Criteria:**
- [ ] Register `/grammar/sutras` resource with MCP server
- [ ] `/grammar/sutras` returns Astadhyayi overview (8 adhyayas, 4 padas each)
- [ ] `/grammar/sutras/{adhyaya}/{pada}` returns sutras in that section
- [ ] `/grammar/sutras/search?q={term}` searches sutras by topic
- [ ] Load data from `data/sutras.yaml`
- [ ] Typecheck passes

---

### US-021: Create sandhi_rules.yaml placeholder
**Description:** As a developer, I need a sandhi rules data file so the resource provider has data to serve.

**Acceptance Criteria:**
- [ ] Create `sanskrit_analyzer/data/sandhi_rules.yaml`
- [ ] Include structure for vowel, consonant, visarga categories
- [ ] Add 5-10 example rules per category with: rule name, sutra reference, before, after, example
- [ ] Mark as placeholder with TODO for full population
- [ ] Typecheck passes (if any Python loading code)

---

### US-022: Create pratyayas.yaml placeholder
**Description:** As a developer, I need a pratyayas data file so the resource provider has data to serve.

**Acceptance Criteria:**
- [ ] Create `sanskrit_analyzer/data/pratyayas.yaml`
- [ ] Include structure for krt, taddhita, tin, sup categories
- [ ] Add 5-10 example pratyayas per category with: name, meaning, grammatical function, example
- [ ] Mark as placeholder with TODO for full population
- [ ] Typecheck passes (if any Python loading code)

---

### US-023: Create sutras.yaml placeholder
**Description:** As a developer, I need a sutras data file so the resource provider has data to serve.

**Acceptance Criteria:**
- [ ] Create `sanskrit_analyzer/data/sutras.yaml`
- [ ] Include structure: adhyaya → pada → sutra list
- [ ] Add 3-5 example sutras per pada for adhyaya 1 (as sample)
- [ ] Each sutra has: number, text (Devanagari), transliteration, meaning
- [ ] Mark as placeholder with TODO for full population
- [ ] Typecheck passes (if any Python loading code)

---

### US-024: Add unit tests for analysis tools
**Description:** As a developer, I need unit tests for analysis tools so I can verify they work correctly.

**Acceptance Criteria:**
- [ ] Create `tests/mcp/test_analysis_tools.py`
- [ ] Test `analyze_sentence` with valid Sanskrit input
- [ ] Test `split_sandhi` returns correct sandhi groups
- [ ] Test `get_morphology` returns valid morphological tags
- [ ] Test `transliterate` correctly converts between scripts
- [ ] Test error handling for invalid inputs
- [ ] All tests pass

---

### US-025: Add unit tests for dhatu tools
**Description:** As a developer, I need unit tests for dhatu tools so I can verify they work correctly.

**Acceptance Criteria:**
- [ ] Create `tests/mcp/test_dhatu_tools.py`
- [ ] Test `lookup_dhatu` with known dhatu (e.g., गम्)
- [ ] Test `search_dhatu` returns relevant results for meaning search
- [ ] Test `conjugate_verb` returns correct conjugation forms
- [ ] Test `list_gana` returns dhatus for valid gana (1-10)
- [ ] Test error handling for unknown dhatu, invalid gana
- [ ] All tests pass

---

### US-026: Add unit tests for grammar tools
**Description:** As a developer, I need unit tests for grammar tools so I can verify they work correctly.

**Acceptance Criteria:**
- [ ] Create `tests/mcp/test_grammar_tools.py`
- [ ] Test `explain_parse` returns multiple parse candidates
- [ ] Test `identify_compound` detects known compound types
- [ ] Test `get_pratyaya` identifies suffixes
- [ ] Test `resolve_ambiguity` returns selected parse with reasoning
- [ ] Test error handling for invalid inputs
- [ ] All tests pass

---

### US-027: Add unit tests for resource providers
**Description:** As a developer, I need unit tests for resource providers so I can verify they serve correct data.

**Acceptance Criteria:**
- [ ] Create `tests/mcp/test_resources.py`
- [ ] Test `/dhatus` resource returns overview
- [ ] Test `/dhatus/gana/1` returns gana 1 dhatus
- [ ] Test `/grammar/sandhi-rules` returns rule index
- [ ] Test `/grammar/pratyayas` returns suffix index
- [ ] Test `/grammar/sutras` returns sutra overview
- [ ] All tests pass

---

### US-028: Add MCP client integration test
**Description:** As a developer, I need an integration test that connects as an MCP client to verify end-to-end functionality.

**Acceptance Criteria:**
- [ ] Create `tests/mcp/test_integration.py`
- [ ] Start MCP server in test fixture
- [ ] Connect using MCP client SDK
- [ ] Call `analyze_sentence` tool and verify response structure
- [ ] Read `/dhatus` resource and verify data
- [ ] Test passes with real HTTP/SSE connection
- [ ] All tests pass

---

### US-029: Add MCP server entry point
**Description:** As a developer, I need a proper entry point so the MCP server can be easily started.

**Acceptance Criteria:**
- [ ] Add `[project.scripts]` entry in pyproject.toml: `sanskrit-mcp = "sanskrit_analyzer.mcp.server:main"`
- [ ] Implement `main()` function that starts the server
- [ ] Support `--host`, `--port`, `--log-level` CLI arguments
- [ ] Server can be started with `sanskrit-mcp` command after install
- [ ] Typecheck passes

---

### US-030: Create homelab deployment configuration
**Description:** As a developer, I need deployment configuration so the MCP server can run on homelab.

**Acceptance Criteria:**
- [ ] Create `docker/mcp/Dockerfile` for MCP server
- [ ] Add `sanskrit-mcp` service to `docker/docker-compose.yml`
- [ ] Configure port 8001 (separate from FastAPI on 8000)
- [ ] Add health check configuration
- [ ] Document deployment in README or separate doc
- [ ] Docker build succeeds

---

### US-031: Add health check endpoint
**Description:** As an operator, I need a health check so monitoring can verify the MCP server is running.

**Acceptance Criteria:**
- [ ] Add `/health` endpoint to MCP server
- [ ] Returns JSON with: status, version, uptime, component health
- [ ] Check analyzer availability
- [ ] Check DhatuDB connectivity
- [ ] Return appropriate HTTP status codes (200 OK, 503 unhealthy)
- [ ] Typecheck passes

---

## Functional Requirements

- FR-1: MCP server must use HTTP/SSE transport for remote access
- FR-2: Server must run on configurable port (default 8001), separate from FastAPI
- FR-3: All 12 tools must be registered and callable via MCP protocol
- FR-4: All 4 resource categories must be browsable via MCP protocol
- FR-5: Tools must accept `verbosity` parameter (minimal|standard|detailed)
- FR-6: Tool responses must return valid JSON matching existing data model schemas
- FR-7: Resources must load data from YAML files in `data/` directory
- FR-8: Server must handle concurrent requests without blocking
- FR-9: Errors must return descriptive messages, not stack traces
- FR-10: Server must be startable via CLI command `sanskrit-mcp`

## Non-Goals (Out of Scope)

- Authentication/authorization (homelab-only deployment for now)
- Rate limiting
- Feedback collection (Phase 4)
- Model training integration (Phases 2-3)
- Full population of grammar reference data (placeholders only)
- Stdio transport mode (HTTP/SSE only)
- Web UI for MCP server

## Technical Considerations

- **MCP SDK:** Use official `mcp` Python package
- **Async:** MCP server should be async to match existing analyzer
- **Reuse:** Tools wrap existing `Analyzer`, `DhatuDB`, and utility classes - no logic duplication
- **Data files:** YAML format for grammar reference data (sandhi_rules, pratyayas, sutras)
- **Testing:** pytest with async support for MCP client tests

## Success Metrics

| Metric | Target |
|--------|--------|
| Tool response latency (simple lookup) | <500ms |
| Tool response latency (full analysis) | <2s |
| All tools callable | 12/12 |
| All resources browsable | 4/4 |
| Test coverage | >80% for MCP module |
| Docker build | Succeeds |

## Open Questions

1. Which version of MCP Python SDK to use? (check latest stable)
2. Should grammar YAML files live in `sanskrit_analyzer/data/` or `data/` at project root?
3. Need to verify DhatuDB works correctly when called from MCP server context

---

*PRD created: 2026-02-02*
*Design reference: docs/plans/2026-02-02-mcp-server-and-training-design.md*
