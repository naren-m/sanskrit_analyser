# Phase A: Integration Completion — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Complete the integration of `sanskrit_analyzer` into `ramayanam` and `yoga_sutras`, replacing all remaining old Sanskrit NLP code with the unified `SanskritAdapter`.

**Architecture:** Each consuming project has a thin `SanskritAdapter` that wraps the `sanskrit_analyzer` library. Controllers/routes call the adapter instead of raw Vidyut/Dharmamitra. This plan finishes the remaining rewiring, deletes old code, adds tests, and cleans up Docker/CI.

**Tech Stack:** Python, Flask, sanskrit_analyzer library, pytest, Docker

**Related spec:** `docs/superpowers/specs/2026-03-31-integration-completion-and-engine-improvements-design.md`

**Scope note:** This plan covers Phase A only. Phase B (engine foundations) and Phase C (capability enhancements) will be separate plans — they operate entirely within `sanskrit_analyzer` and have no dependency on Phase A.

---

### Task 1: Ramayanam — Rewire dhatu_controller.py

**Context:** The dhatu controller at `~/Projects/ramayanam/api/controllers/dhatu_controller.py` makes direct SQLite queries against `comprehensive_dhatu_database.db`. It needs to be rewired to use `SanskritAdapter.lookup_dhatu()` for the search endpoint, while keeping the database-only endpoints (stats, all, by-id, by-gana, by-pada) as they are — the adapter's `lookup_dhatu()` only handles single-root lookups, not bulk queries.

**Repo:** `~/Projects/ramayanam` (branch: `feature/sanskrit-analyzer-integration`)

**Files:**
- Modify: `~/Projects/ramayanam/api/controllers/dhatu_controller.py`

- [ ] **Step 1: Add SanskritAdapter import and instance**

At the top of `~/Projects/ramayanam/api/controllers/dhatu_controller.py`, after the existing imports (around line 17), add:

```python
from api.services.sanskrit_adapter import get_sanskrit_adapter
```

- [ ] **Step 2: Add an adapter-backed search route alongside the existing one**

The current `/search` endpoint (lines 156-197) does raw SQL LIKE queries. Instead of replacing it entirely (the SQLite DB has fields like `dhatu_ipa`, `all_meanings` that the adapter doesn't provide), add a supplementary method that enriches search results with analyzer data when a dhatu match is found.

Replace the `search_dhatus` function body (lines 156-197) with:

```python
@dhatu_blueprint.route("/search", methods=["POST"])
def search_dhatus():
    """Search dhatus based on query and type"""
    data = request.get_json()
    if not data:
        return jsonify({"error": "Invalid JSON"}), 400

    query = data.get("query", "").strip()
    search_type = data.get("search_type", "all").lower()
    limit = data.get("limit", 100)

    try:
        with get_db() as conn:
            if search_type == "exact":
                sql = "SELECT * FROM dhatus WHERE dhatu_devanagari = ? OR dhatu_transliterated = ? OR dhatu_ipa = ? LIMIT ?"
                params = (query, query, query, limit)
            elif search_type == "dhatu":
                sql = "SELECT * FROM dhatus WHERE dhatu_devanagari LIKE ? OR dhatu_transliterated LIKE ? OR dhatu_ipa LIKE ? LIMIT ?"
                params = (f"%{query}%", f"%{query}%", f"%{query}%", limit)
            elif search_type == "meaning":
                sql = "SELECT * FROM dhatus WHERE meaning_english LIKE ? OR all_meanings LIKE ? LIMIT ?"
                params = (f"%{query}%", f"%{query}%", limit)
            else:  # "all"
                sql = "SELECT * FROM dhatus WHERE dhatu_devanagari LIKE ? OR dhatu_transliterated LIKE ? OR dhatu_ipa LIKE ? OR meaning_english LIKE ? OR all_meanings LIKE ? LIMIT ?"
                like_query = f"%{query}%"
                params = (like_query, like_query, like_query, like_query, like_query, limit)

            cursor = conn.execute(sql, params)
            results = [dict(row) for row in cursor.fetchall()]

        # Enrich with analyzer data if available
        adapter = get_sanskrit_adapter()
        if search_type in ("exact", "dhatu") and len(results) <= 10:
            for result_row in results:
                transliterated = result_row.get("dhatu_transliterated", "")
                if transliterated:
                    dhatu_info = adapter.lookup_dhatu(transliterated)
                    if dhatu_info:
                        result_row["analyzer_info"] = {
                            "dhatu": dhatu_info.dhatu,
                            "gana": dhatu_info.gana.value if dhatu_info.gana else None,
                            "meaning": dhatu_info.meaning,
                        }

        return jsonify(
            {
                "query": query,
                "search_type": search_type,
                "count": len(results),
                "results": results,
            }
        )

    except Exception as e:
        logger.error(f"Search error: {e}")
        return jsonify({"error": str(e)}), 500
```

- [ ] **Step 3: Commit**

```bash
cd ~/Projects/ramayanam
git add api/controllers/dhatu_controller.py
git commit -m "Enrich dhatu search with sanskrit_analyzer lookup"
```

---

### Task 2: Ramayanam — Fix broken tests

**Context:** `tests/unit/test_dharmamitra_service.py` imports from `api.services.dharmamitra_service` which was deleted. This file needs to be deleted and replaced with tests for the new `SanskritAdapter`.

**Repo:** `~/Projects/ramayanam` (branch: `feature/sanskrit-analyzer-integration`)

**Files:**
- Delete: `~/Projects/ramayanam/tests/unit/test_dharmamitra_service.py`
- Create: `~/Projects/ramayanam/tests/unit/test_sanskrit_adapter.py`

- [ ] **Step 1: Delete the broken test file**

```bash
cd ~/Projects/ramayanam
rm tests/unit/test_dharmamitra_service.py
```

- [ ] **Step 2: Create test file for SanskritAdapter**

Create `~/Projects/ramayanam/tests/unit/test_sanskrit_adapter.py`:

```python
"""Integration tests for the SanskritAdapter.

Tests use the real sanskrit_analyzer library to verify the adapter
actually works end-to-end. Tests skip gracefully if engines aren't available.
"""

import pytest

from api.services.sanskrit_adapter import SanskritAdapter, get_sanskrit_adapter


@pytest.fixture
def adapter():
    """Create a real SanskritAdapter instance."""
    try:
        a = SanskritAdapter()
        _ = a.analyzer  # Trigger lazy init
        return a
    except Exception as e:
        pytest.skip(f"sanskrit_analyzer not available: {e}")


class TestSanskritAdapter:
    """Tests for SanskritAdapter with real Analyzer."""

    def test_analyzer_initializes(self, adapter):
        """Test that the real Analyzer initializes successfully."""
        assert adapter.analyzer is not None

    def test_singleton_instance(self):
        """Test that get_sanskrit_adapter returns same instance."""
        import api.services.sanskrit_adapter as mod

        mod._adapter_instance = None  # Reset
        a1 = get_sanskrit_adapter()
        a2 = get_sanskrit_adapter()
        assert a1 is a2
        mod._adapter_instance = None  # Cleanup

    def test_analyze_sloka_sync(self, adapter):
        """Test sync analysis of a simple Sanskrit phrase."""
        result = adapter.analyze_sloka_sync("रामः गच्छति")
        assert result is not None
        assert result.confidence.overall > 0.0
        assert len(result.parse_forest) > 0

    def test_get_morphology_sync(self, adapter):
        """Test morphology lookup for a known word."""
        result = adapter.get_morphology_sync("गच्छति")
        # Should return a dict with morphological info (or empty if engine unavailable)
        assert isinstance(result, dict)

    def test_get_morphology_sync_empty_input(self, adapter):
        """Test morphology lookup with empty string."""
        result = adapter.get_morphology_sync("")
        assert result == {}

    def test_lookup_dhatu(self, adapter):
        """Test dhatu lookup for a known root."""
        result = adapter.lookup_dhatu("gam")
        # May return None if dhatu DB doesn't have this entry
        if result is not None:
            assert result.dhatu is not None

    def test_dictionary_lookup(self, adapter):
        """Test dictionary lookup returns a list."""
        result = adapter.dictionary_lookup("rAma")
        assert isinstance(result, list)

    def test_extract_entities_for_graph_sync(self, adapter):
        """Test entity extraction returns list of dicts."""
        result = adapter.extract_entities_for_graph_sync("रामः गच्छति")
        assert isinstance(result, list)
        for entity in result:
            assert "lemma" in entity
```

- [ ] **Step 3: Run the new tests**

```bash
cd ~/Projects/ramayanam
python -m pytest tests/unit/test_sanskrit_adapter.py -v
```

Expected: All tests PASS (or skip if sanskrit_analyzer not installed in the venv).

- [ ] **Step 4: Commit**

```bash
cd ~/Projects/ramayanam
git add -A tests/unit/test_dharmamitra_service.py tests/unit/test_sanskrit_adapter.py
git commit -m "Replace broken dharmamitra tests with sanskrit_adapter tests"
```

---

### Task 3: Yoga Sutras — Replace dictionary_service.py with adapter

**Context:** The dictionary route `/api/dictionary/<word>` in `~/Projects/yoga_sutras/backend/app/routes/dictionary_routes.py` still uses `DictionaryService` (which depends on a SQLAlchemy `Dictionary` model and `rapidfuzz`). The adapter's `dictionary_lookup()` method provides equivalent functionality. However, `DictionaryService` provides fuzzy matching and multi-dictionary display formatting that `sanskrit_analyzer.dictionary_lookup()` may not replicate exactly. We should keep the existing `DictionaryService` for now (it doesn't depend on any deleted code) and mark this decision in a comment.

**DECISION CHANGE:** After reading `dictionary_service.py`, it imports from `app.models.dictionary` (SQLAlchemy models), `app.db`, `indic_transliteration`, and `rapidfuzz`. These are project-specific dependencies for the Yoga Sutras dictionary database (MW, Apte dictionaries stored in SQLite via SQLAlchemy). This is NOT the same as the old Vidyut/Dharmamitra services — it's the project's own dictionary database layer. **Keep it as-is.** The spec's requirement was to remove old *Sanskrit NLP* services, not the project's own dictionary DB.

**Repo:** `~/Projects/yoga_sutras` (branch: `feature/sanskrit-analyzer-integration`)

**Files:**
- Modify: `~/Projects/yoga_sutras/backend/app/routes/dictionary_routes.py` (add comment documenting decision)

- [ ] **Step 1: Add documentation comment to dictionary_routes.py**

At the top of `~/Projects/yoga_sutras/backend/app/routes/dictionary_routes.py`, after line 1, add a comment:

```python
"""Dictionary and Sanskrit analysis routes for Yoga Sutras API.

Provides REST endpoints for dictionary lookups, sandhi splitting,
and morphological analysis using the unified sanskrit_analyzer.

Note: DictionaryService is kept because it wraps the project's own
MW/Apte dictionary SQLite database with fuzzy matching — this is
project-specific, not part of the old Vidyut/Dharmamitra NLP code.
"""
```

- [ ] **Step 2: Commit**

```bash
cd ~/Projects/yoga_sutras
git add backend/app/routes/dictionary_routes.py
git commit -m "Document decision to keep DictionaryService (project-specific, not old NLP)"
```

---

### Task 4: Yoga Sutras — Delete vidyut-data directory

**Context:** `data/vidyut-data/` (77MB) contains old Vidyut data files (chandas, cheda, kosha, prakriya, sandhi). The `sanskrit_analyzer` library bundles its own data. This directory is no longer referenced by any code on the integration branch.

**Repo:** `~/Projects/yoga_sutras` (branch: `feature/sanskrit-analyzer-integration`)

**Files:**
- Delete: `~/Projects/yoga_sutras/data/vidyut-data/`

- [ ] **Step 1: Verify no code references vidyut-data**

```bash
cd ~/Projects/yoga_sutras
grep -r "vidyut-data" --include="*.py" --include="*.yml" --include="*.yaml" --include="*.txt" --include="*.cfg" --include="*.toml" . 2>/dev/null || echo "No references found"
```

Expected: No references found (or only in deleted files).

- [ ] **Step 2: Delete the directory**

```bash
cd ~/Projects/yoga_sutras
rm -rf data/vidyut-data
```

- [ ] **Step 3: Commit**

```bash
cd ~/Projects/yoga_sutras
git add -A data/vidyut-data
git commit -m "Remove vidyut-data (77MB) — now bundled in sanskrit_analyzer"
```

---

### Task 5: Yoga Sutras — Add adapter tests

**Context:** The Yoga Sutras project has no test files. Create basic tests for the `SanskritAdapter` and the route integration.

**Repo:** `~/Projects/yoga_sutras` (branch: `feature/sanskrit-analyzer-integration`)

**Files:**
- Create: `~/Projects/yoga_sutras/backend/tests/__init__.py`
- Create: `~/Projects/yoga_sutras/backend/tests/test_sanskrit_adapter.py`

- [ ] **Step 1: Create test directory and init file**

```bash
mkdir -p ~/Projects/yoga_sutras/backend/tests
touch ~/Projects/yoga_sutras/backend/tests/__init__.py
```

- [ ] **Step 2: Create adapter tests**

Create `~/Projects/yoga_sutras/backend/tests/test_sanskrit_adapter.py`:

```python
"""Integration tests for the Yoga Sutras SanskritAdapter.

Tests use the real sanskrit_analyzer library to verify the adapter
actually works end-to-end. Tests skip gracefully if engines aren't available.
"""

import pytest

from app.services.sanskrit_adapter import SanskritAdapter, get_sanskrit_adapter


@pytest.fixture
def adapter():
    """Create a real SanskritAdapter instance."""
    try:
        a = SanskritAdapter()
        _ = a.analyzer  # Trigger lazy init
        return a
    except Exception as e:
        pytest.skip(f"sanskrit_analyzer not available: {e}")


class TestSanskritAdapter:
    """Tests for SanskritAdapter with real Analyzer."""

    def test_analyzer_initializes(self, adapter):
        """Test that the real Analyzer initializes successfully."""
        assert adapter.analyzer is not None

    def test_is_available(self, adapter):
        """Test is_available returns True when initialized."""
        assert adapter.is_available() is True

    def test_singleton_instance(self):
        """Test get_sanskrit_adapter returns same instance."""
        import app.services.sanskrit_adapter as mod

        mod._adapter_instance = None
        a1 = get_sanskrit_adapter()
        a2 = get_sanskrit_adapter()
        assert a1 is a2
        mod._adapter_instance = None

    def test_split_returns_backwards_compatible_dict(self, adapter):
        """Test split() returns the old SandhiService response format."""
        result = adapter.split("yogaścittavṛttinirodhaḥ")

        assert "splits" in result
        assert "original" in result
        assert "engine_available" in result
        assert result["engine_available"] is True
        assert isinstance(result["splits"], list)

    def test_split_has_expected_keys(self, adapter):
        """Test split tokens have text and lemma keys."""
        result = adapter.split("rāmaḥ")

        if result["splits"]:
            token = result["splits"][0]
            assert "text" in token
            assert "lemma" in token

    def test_get_morphology_sync(self, adapter):
        """Test morphology analysis for a known word."""
        result = adapter.get_morphology_sync("गच्छति")
        # Returns dict or None
        if result is not None:
            assert isinstance(result, dict)

    def test_get_status(self, adapter):
        """Test get_status returns service info."""
        status = adapter.get_status()
        assert status["service"] == "sanskrit_analyzer"
        assert status["available"] is True

    def test_dictionary_lookup(self, adapter):
        """Test dictionary_lookup returns a list."""
        result = adapter.dictionary_lookup("yoga")
        assert isinstance(result, list)

    def test_analyze_word_sync(self, adapter):
        """Test word analysis returns expected format."""
        result = adapter.analyze_word_sync("रामः")
        assert "word" in result
        assert result["word"] == "रामः"
```

- [ ] **Step 3: Run the tests**

```bash
cd ~/Projects/yoga_sutras/backend
python -m pytest tests/test_sanskrit_adapter.py -v
```

Expected: Tests pass (may need adjusting for import paths depending on project's test setup).

- [ ] **Step 4: Commit**

```bash
cd ~/Projects/yoga_sutras
git add backend/tests/
git commit -m "Add unit tests for SanskritAdapter"
```

---

### Task 6: Yoga Sutras — Update requirements.txt for production

**Context:** The `backend/requirements.txt` currently points to a local file path (`git+file:///...@feature/sanskrit-analyzer-integration`). This needs to point to the GitHub repo and main branch for production use.

**Repo:** `~/Projects/yoga_sutras` (branch: `feature/sanskrit-analyzer-integration`)

**Files:**
- Modify: `~/Projects/yoga_sutras/backend/requirements.txt`

- [ ] **Step 1: Update the dependency URL**

In `~/Projects/yoga_sutras/backend/requirements.txt`, replace line 12:

```
sanskrit-analyzer @ git+file:///Users/narenmudivarthy/Projects/sanskrit_analyzer@feature/sanskrit-analyzer-integration
```

with:

```
sanskrit-analyzer @ git+https://github.com/naren-m/sanskrit_analyser.git@main
```

- [ ] **Step 2: Commit**

```bash
cd ~/Projects/yoga_sutras
git add backend/requirements.txt
git commit -m "Update sanskrit-analyzer dependency to GitHub main branch"
```

---

### Task 7: Cleanup — Update READMEs

**Context:** Both consuming projects should document the `sanskrit_analyzer` dependency and remove references to direct Vidyut/Dharmamitra usage.

**Repos:** `~/Projects/ramayanam` and `~/Projects/yoga_sutras`

**Files:**
- Modify: `~/Projects/ramayanam/README.md` (add note about sanskrit_analyzer dependency)
- Modify: `~/Projects/yoga_sutras/README.md` (add note about sanskrit_analyzer dependency)

- [ ] **Step 1: Check current README contents for Sanskrit NLP references**

```bash
cd ~/Projects/ramayanam && grep -n -i "vidyut\|dharmamitra\|sanskrit.*analyz" README.md | head -20
cd ~/Projects/yoga_sutras && grep -n -i "vidyut\|dharmamitra\|sanskrit.*analyz" README.md | head -20
```

- [ ] **Step 2: Update Ramayanam README**

Find the dependencies or technology section in `~/Projects/ramayanam/README.md` and add a note:

```markdown
### Sanskrit Analysis
Sanskrit text analysis (morphology, sandhi splitting, dhatu lookup) is powered by the [sanskrit_analyzer](https://github.com/naren-m/sanskrit_analyser) library, which provides a 3-engine ensemble parser (Vidyut + Dharmamitra + Heritage).
```

Remove any references to direct Vidyut or Dharmamitra usage if present.

- [ ] **Step 3: Update Yoga Sutras README**

Find the dependencies or technology section in `~/Projects/yoga_sutras/README.md` and add a similar note:

```markdown
### Sanskrit Analysis
Sanskrit text analysis (sandhi splitting, morphology, word analysis) uses the [sanskrit_analyzer](https://github.com/naren-m/sanskrit_analyser) library via a thin `SanskritAdapter` wrapper.
```

Remove any references to direct Vidyut or Dharmamitra usage if present.

- [ ] **Step 4: Commit in each repo**

```bash
cd ~/Projects/ramayanam
git add README.md
git commit -m "Document sanskrit_analyzer dependency in README"

cd ~/Projects/yoga_sutras
git add README.md
git commit -m "Document sanskrit_analyzer dependency in README"
```

---

### Task 8: Cleanup — Update Docker files

**Context:** The Yoga Sutras `docker-compose.yml` mounts `./data:/app/data` which includes the now-deleted `vidyut-data/`. No explicit volume mount for vidyut-data exists (it was just inside the `./data` mount), so Docker config doesn't need changes. However, ensure the Docker build can install `sanskrit_analyzer` from git.

**Repos:** `~/Projects/yoga_sutras`

**Files:**
- Modify: `~/Projects/yoga_sutras/docker/Dockerfile.backend` (ensure git is installed for pip git dependency)

- [ ] **Step 1: Read the Dockerfile**

```bash
cat ~/Projects/yoga_sutras/docker/Dockerfile.backend
```

- [ ] **Step 2: Ensure git is available in the Docker image**

If `git` is not already installed in the Dockerfile, add it before `pip install`. For example, if using a Debian/Ubuntu-based image:

```dockerfile
RUN apt-get update && apt-get install -y git && rm -rf /var/lib/apt/lists/*
```

If using Alpine:

```dockerfile
RUN apk add --no-cache git
```

This is needed because `pip install` of a `git+https://` dependency requires `git` to be present.

- [ ] **Step 3: Commit**

```bash
cd ~/Projects/yoga_sutras
git add docker/Dockerfile.backend
git commit -m "Ensure git available in Docker for sanskrit-analyzer dependency"
```

---

### Task 9: Validation — Run all test suites

**Context:** Final validation step to ensure everything works across all three repos.

**Repos:** All three

- [ ] **Step 1: Run sanskrit_analyzer tests**

```bash
cd ~/Projects/sanskrit_analyzer
uv run pytest
```

Expected: 515 tests pass.

- [ ] **Step 2: Run ramayanam tests**

```bash
cd ~/Projects/ramayanam
python -m pytest tests/unit/test_sanskrit_adapter.py -v
```

Expected: All adapter tests pass.

- [ ] **Step 3: Run yoga_sutras tests**

```bash
cd ~/Projects/yoga_sutras/backend
python -m pytest tests/test_sanskrit_adapter.py -v
```

Expected: All adapter tests pass.

- [ ] **Step 4: Verify no imports of deleted services remain**

```bash
cd ~/Projects/ramayanam
grep -r "dharmamitra_service\|sandhi_service\|morphology_service" --include="*.py" . | grep -v __pycache__ | grep -v ".pyc"

cd ~/Projects/yoga_sutras
grep -r "dharmamitra_service\|sandhi_service\|morphology_service" --include="*.py" . | grep -v __pycache__ | grep -v ".pyc"
```

Expected: No references to deleted services (except possibly in git-related or migration notes).

---

### Task 10: Ramayanam — Check guru_service.py (low priority)

**Context:** Per spec A1.3, guru_service.py should be checked. From reading the first 80 lines, it's a RAG Q&A service with no imports of deleted Sanskrit NLP services. It uses its own LLM-based pipeline. Only update if it references deleted code.

**Repo:** `~/Projects/ramayanam` (branch: `feature/sanskrit-analyzer-integration`)

**Files:**
- Read: `~/Projects/ramayanam/api/services/guru_service.py`

- [ ] **Step 1: Check for deleted service imports**

```bash
cd ~/Projects/ramayanam
grep -n "dharmamitra\|sandhi_service\|morphology_service\|from.*vidyut" api/services/guru_service.py
```

Expected: No matches. If no matches found, no changes needed — guru_service.py is independent.

- [ ] **Step 2: If references found, rewire them**

If any deleted service imports are found, replace them with `SanskritAdapter` calls following the same pattern as `morphology_controller.py`.

- [ ] **Step 3: Commit if changes were made**

```bash
cd ~/Projects/ramayanam
git add api/services/guru_service.py
git commit -m "Rewire guru_service to use SanskritAdapter"
```

(Only if changes were needed.)

---

### Task 11: Cleanup — Update CI/CD for git dependency

**Context:** Both consuming projects install `sanskrit_analyzer` from a git URL. CI/CD pipelines need to be able to resolve this. If the repo is private, a deploy key or token is needed.

**Repos:** `~/Projects/ramayanam` and `~/Projects/yoga_sutras`

- [ ] **Step 1: Check ramayanam CI configuration**

```bash
cd ~/Projects/ramayanam
ls jenkins/ .github/workflows/ 2>/dev/null
```

- [ ] **Step 2: Check yoga_sutras CI configuration**

```bash
cd ~/Projects/yoga_sutras
ls jenkins/ .github/workflows/ 2>/dev/null
```

- [ ] **Step 3: Ensure Dockerfiles have git installed**

For each project's Dockerfile that runs `pip install -r requirements.txt`, ensure `git` is available (needed for `pip install git+https://...`).

Check with:
```bash
grep -n "git" ~/Projects/ramayanam/Dockerfile* ~/Projects/ramayanam/docker/Dockerfile* 2>/dev/null
grep -n "git" ~/Projects/yoga_sutras/docker/Dockerfile* 2>/dev/null
```

If `git` is not installed in the Docker image, add before pip install:

For Debian/Ubuntu-based images:
```dockerfile
RUN apt-get update && apt-get install -y git && rm -rf /var/lib/apt/lists/*
```

- [ ] **Step 4: If repos are private, document access requirements**

If `sanskrit_analyser` is a private GitHub repo, the CI system needs a way to authenticate. Add a note to each project's deployment docs:

```
Note: CI requires git access to https://github.com/naren-m/sanskrit_analyser.git
Configure a GitHub deploy key or personal access token in CI environment.
```

- [ ] **Step 5: Commit any changes**

```bash
cd ~/Projects/ramayanam && git add -A && git diff --cached --quiet || git commit -m "Ensure CI can install sanskrit-analyzer git dependency"
cd ~/Projects/yoga_sutras && git add -A && git diff --cached --quiet || git commit -m "Ensure CI can install sanskrit-analyzer git dependency"
```
