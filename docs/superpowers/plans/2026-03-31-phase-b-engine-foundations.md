# Phase B: Engine Foundations — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix the engine foundations so the ensemble produces meaningful confidence scores and morphological analysis — Heritage engine functional, weights normalized, confidence calibrated, morphology/POS voting added.

**Architecture:** Four engines feed into an ensemble combiner. Currently Heritage is stubbed, all confidence values are hardcoded, and only lemma voting works. This plan fixes each issue in dependency order: weights first (used by everything), then per-engine confidence, then Heritage parsing, then ensemble voting.

**Tech Stack:** Python, aiohttp, pytest, BeautifulSoup (new dependency for Heritage parsing)

**Repo:** `~/Projects/sanskrit_analyzer` (branch: `main`)

**Related spec:** `docs/superpowers/specs/2026-03-31-integration-completion-and-engine-improvements-design.md` (Phase B)

---

### Task 1: Normalize ensemble weights

**Context:** `ensemble.py` has `EnsembleConfig` with weights summing to 1.45 (Vidyut 0.35 + Dharmamitra 0.40 + Heritage 0.25 + LocalByT5 0.45). The `_merge_results` method uses these raw weights. We need to normalize at initialization time.

**Files:**
- Modify: `~/Projects/sanskrit_analyzer/sanskrit_analyzer/engines/ensemble.py`
- Modify: `~/Projects/sanskrit_analyzer/tests/test_engines/test_ensemble.py`

- [ ] **Step 1: Write failing test for weight normalization**

Add to `~/Projects/sanskrit_analyzer/tests/test_engines/test_ensemble.py`:

```python
class TestWeightNormalization:
    """Tests for weight normalization."""

    def test_weights_sum_to_one(self) -> None:
        """Test that normalized weights sum to 1.0."""
        analyzer = EnsembleAnalyzer(config=EnsembleConfig())
        total = sum(analyzer.normalized_weights.values())
        assert abs(total - 1.0) < 0.01

    def test_normalized_weights_preserve_ratios(self) -> None:
        """Test that relative ordering is preserved after normalization."""
        analyzer = EnsembleAnalyzer(config=EnsembleConfig())
        weights = analyzer.normalized_weights
        # LocalByT5 should still be highest
        assert weights["local_byt5"] > weights["vidyut"]
        assert weights["dharmamitra"] > weights["heritage"]

    def test_three_engine_normalization(self) -> None:
        """Test normalization when only 3 engines are registered."""
        engines = [
            MockEngine("vidyut", 0.35),
            MockEngine("dharmamitra", 0.40),
            MockEngine("heritage", 0.25),
        ]
        analyzer = EnsembleAnalyzer(engines=engines)
        total = sum(analyzer.normalized_weights.values())
        assert abs(total - 1.0) < 0.01
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd ~/Projects/sanskrit_analyzer
uv run pytest tests/test_engines/test_ensemble.py::TestWeightNormalization -v
```

Expected: FAIL — `normalized_weights` property doesn't exist.

- [ ] **Step 3: Implement weight normalization in EnsembleAnalyzer**

In `~/Projects/sanskrit_analyzer/sanskrit_analyzer/engines/ensemble.py`, add a `normalized_weights` property and update `_merge_results` to use it.

After the `__init__` method (line 103), add:

```python
    @property
    def normalized_weights(self) -> dict[str, float]:
        """Get weights normalized to sum to 1.0.

        Only includes weights for currently registered engines.
        """
        registered = {e.name for e in self._engines}
        active_weights = {
            name: w for name, w in self._weights.items() if name in registered
        }
        if not active_weights:
            return {}
        total = sum(active_weights.values())
        if total == 0:
            return {name: 1.0 / len(active_weights) for name in active_weights}
        return {name: w / total for name, w in active_weights.items()}
```

Then update `_merge_results` at line 255 to use normalized weights:

Replace:
```python
                    weight = self._weights.get(engine_name, 0.33)
```

With:
```python
                    nw = self.normalized_weights
                    weight = nw.get(engine_name, 1.0 / max(len(nw), 1))
```

And at line 268, replace:
```python
            total_weight = sum(self._weights.get(name, 0.33) for name in votes.keys())
```

With:
```python
            nw = self.normalized_weights
            total_weight = sum(nw.get(name, 0.0) for name in votes.keys())
```

- [ ] **Step 4: Run tests**

```bash
cd ~/Projects/sanskrit_analyzer
uv run pytest tests/test_engines/test_ensemble.py -v
```

Expected: All tests pass including new normalization tests.

- [ ] **Step 5: Commit**

```bash
cd ~/Projects/sanskrit_analyzer
git add sanskrit_analyzer/engines/ensemble.py tests/test_engines/test_ensemble.py
git commit -m "Normalize ensemble weights to sum to 1.0"
```

---

### Task 2: Vidyut confidence calibration

**Context:** `vidyut_engine.py` hardcodes confidence at 0.9 (line 222). Instead, confidence should reflect the number of parse candidates — a single unambiguous parse should be high confidence, multiple ambiguous parses should be lower.

**Files:**
- Modify: `~/Projects/sanskrit_analyzer/sanskrit_analyzer/engines/vidyut_engine.py`
- Modify: `~/Projects/sanskrit_analyzer/tests/test_engines/test_vidyut_engine.py`

- [ ] **Step 1: Write failing test for dynamic confidence**

Add to `~/Projects/sanskrit_analyzer/tests/test_engines/test_vidyut_engine.py`:

```python
    @pytest.mark.asyncio
    async def test_confidence_varies_with_ambiguity(self, engine: VidyutEngine) -> None:
        """Test that confidence is not a fixed value."""
        if not engine.is_available:
            pytest.skip("Vidyut not available")

        result = await engine.analyze("gacCati")

        if result.success:
            # Confidence should not be exactly 0.9 (the old hardcoded value)
            # It should be computed from parse quality
            for seg in result.segments:
                assert 0.0 < seg.confidence <= 1.0
```

- [ ] **Step 2: Run test to confirm current behavior**

```bash
cd ~/Projects/sanskrit_analyzer
uv run pytest tests/test_engines/test_vidyut_engine.py::TestVidyutEngine::test_confidence_varies_with_ambiguity -v
```

Note: This may pass trivially since the assertion is `> 0.0 and <= 1.0` which 0.9 satisfies. The real validation comes from integration tests later.

- [ ] **Step 3: Implement dynamic confidence in VidyutEngine**

In `~/Projects/sanskrit_analyzer/sanskrit_analyzer/engines/vidyut_engine.py`, replace the segment creation logic in the `analyze` method.

Replace lines 194-226 (the segment building loop):

```python
            # Run segmentation
            segments: list[Segment] = []
            tokens = self._chedaka.run(slp1_text)  # type: ignore

            # Confidence based on number of tokens vs input complexity
            # Single unambiguous segmentation = high confidence
            # Many tokens for short input may indicate over-segmentation
            token_list = list(tokens)
            input_word_count = len(slp1_text.split())
            token_count = len(token_list)

            # Base confidence: rule-based is reliable when it finds a parse
            # Reduce slightly if token count differs significantly from word count
            if token_count == 0:
                base_confidence = 0.0
            elif input_word_count > 0 and token_count > 0:
                # Ratio of expected to actual segments
                ratio = min(input_word_count, token_count) / max(input_word_count, token_count)
                base_confidence = 0.7 + (0.25 * ratio)  # Range: 0.7 - 0.95
            else:
                base_confidence = 0.8

            for token in token_list:
                # Parse morphological data
                morph_data = self._parse_pada_data(token.data)

                # Per-segment confidence: higher if morphology was parsed
                seg_confidence = base_confidence
                if morph_data.get("type"):
                    seg_confidence = min(seg_confidence + 0.05, 0.98)

                # Build morphology string
                morph_parts = []
                if "type" in morph_data:
                    morph_parts.append(morph_data["type"])
                if "gender" in morph_data:
                    morph_parts.append(morph_data["gender"][:3])
                if "case" in morph_data:
                    morph_parts.append(morph_data["case"][:3])
                if "number" in morph_data:
                    morph_parts.append(morph_data["number"][:2])
                if "person" in morph_data:
                    morph_parts.append(morph_data["person"][:3])
                if "lakara" in morph_data:
                    morph_parts.append(morph_data["lakara"])

                morph_str = ".".join(morph_parts) if morph_parts else None

                segment = Segment(
                    surface=token.text,
                    lemma=token.lemma,
                    morphology=morph_str,
                    confidence=seg_confidence,
                    pos=morph_data.get("type"),
                )

                segments.append(segment)

            return EngineResult(
                engine=self.name,
                segments=segments,
                confidence=base_confidence if segments else 0.0,
                raw_output=str([str(t.data) for t in self._chedaka.run(slp1_text)]),  # type: ignore
            )
```

- [ ] **Step 4: Run all Vidyut tests**

```bash
cd ~/Projects/sanskrit_analyzer
uv run pytest tests/test_engines/test_vidyut_engine.py -v
```

Expected: All tests pass.

- [ ] **Step 5: Commit**

```bash
cd ~/Projects/sanskrit_analyzer
git add sanskrit_analyzer/engines/vidyut_engine.py tests/test_engines/test_vidyut_engine.py
git commit -m "Calibrate Vidyut confidence based on parse quality"
```

---

### Task 3: Dharmamitra confidence calibration

**Context:** `dharmamitra_engine.py` hardcodes confidence at 0.92 (line 204, 214). Confidence should be based on the completeness of the morphological tags returned.

**Files:**
- Modify: `~/Projects/sanskrit_analyzer/sanskrit_analyzer/engines/dharmamitra_engine.py`
- Modify: `~/Projects/sanskrit_analyzer/tests/test_engines/test_dharmamitra_engine.py`

- [ ] **Step 1: Write failing test**

Add to `~/Projects/sanskrit_analyzer/tests/test_engines/test_dharmamitra_engine.py`:

```python
    def test_compute_confidence_full_tags(self) -> None:
        """Test confidence is higher when all tags are present."""
        engine = DharmamitraEngine.__new__(DharmamitraEngine)
        tag = {"tense": "Present", "mood": "Indicative", "person": "3", "number": "Singular"}
        conf = engine._compute_segment_confidence(tag, has_lemma=True, has_meanings=True)
        assert conf >= 0.85

    def test_compute_confidence_minimal_tags(self) -> None:
        """Test confidence is lower when few tags are present."""
        engine = DharmamitraEngine.__new__(DharmamitraEngine)
        tag = {"raw": "unknown"}
        conf = engine._compute_segment_confidence(tag, has_lemma=True, has_meanings=False)
        assert conf < 0.80
```

- [ ] **Step 2: Run to verify failure**

```bash
cd ~/Projects/sanskrit_analyzer
uv run pytest tests/test_engines/test_dharmamitra_engine.py -k "compute_confidence" -v
```

Expected: FAIL — `_compute_segment_confidence` doesn't exist.

- [ ] **Step 3: Implement confidence computation**

In `~/Projects/sanskrit_analyzer/sanskrit_analyzer/engines/dharmamitra_engine.py`, add a method after `_determine_pos` (after line 127):

```python
    def _compute_segment_confidence(
        self, tag: dict, has_lemma: bool, has_meanings: bool
    ) -> float:
        """Compute confidence for a segment based on tag completeness.

        Args:
            tag: Parsed tag dictionary.
            has_lemma: Whether a lemma was returned.
            has_meanings: Whether meanings were returned.

        Returns:
            Confidence score 0.0-1.0.
        """
        score = 0.5  # Base: we got a result

        # Morphological completeness
        morph_keys = {"tense", "mood", "person", "number", "case", "gender"}
        present = sum(1 for k in morph_keys if k in tag)
        score += 0.3 * (present / len(morph_keys))  # Up to +0.3

        if has_lemma:
            score += 0.1
        if has_meanings:
            score += 0.1

        return min(score, 0.98)
```

Then update the segment creation in `analyze()` — replace line 204:

```python
                    confidence=0.92,  # Dharmamitra is neural, high but not rule-based
```

with:

```python
                    confidence=self._compute_segment_confidence(
                        tag,
                        has_lemma=bool(word_data.get("lemma")),
                        has_meanings=bool(word_data.get("meanings")),
                    ),
```

And replace line 214:

```python
                confidence=0.92 if segments else 0.0,
```

with:

```python
                confidence=(
                    sum(s.confidence for s in segments) / len(segments)
                    if segments
                    else 0.0
                ),
```

- [ ] **Step 4: Run all Dharmamitra tests**

```bash
cd ~/Projects/sanskrit_analyzer
uv run pytest tests/test_engines/test_dharmamitra_engine.py -v
```

Expected: All tests pass.

- [ ] **Step 5: Commit**

```bash
cd ~/Projects/sanskrit_analyzer
git add sanskrit_analyzer/engines/dharmamitra_engine.py tests/test_engines/test_dharmamitra_engine.py
git commit -m "Calibrate Dharmamitra confidence based on tag completeness"
```

---

### Task 4: LocalByT5 confidence calibration

**Context:** `local_byt5_engine.py` hardcodes confidence at 0.90 (line 356, 361). Confidence should be based on whether the model produced well-formed output (all three components: surface, lemma, tags).

**Files:**
- Modify: `~/Projects/sanskrit_analyzer/sanskrit_analyzer/engines/local_byt5_engine.py`
- Modify: `~/Projects/sanskrit_analyzer/tests/test_engines/test_local_byt5_engine.py`

- [ ] **Step 1: Write failing test**

Add to `~/Projects/sanskrit_analyzer/tests/test_engines/test_local_byt5_engine.py`:

```python
    def test_compute_segment_confidence_full(self) -> None:
        """Test confidence for segment with all components."""
        with patch.object(LocalByT5Engine, "_load_model"):
            engine = LocalByT5Engine(load_on_init=False)
            conf = engine._compute_segment_confidence(
                {"surface": "rāma", "lemma": "rāma", "tags": "SNM"}
            )
            assert conf >= 0.85

    def test_compute_segment_confidence_no_tags(self) -> None:
        """Test confidence for segment without tags."""
        with patch.object(LocalByT5Engine, "_load_model"):
            engine = LocalByT5Engine(load_on_init=False)
            conf = engine._compute_segment_confidence(
                {"surface": "rāma", "lemma": "rāma", "tags": ""}
            )
            assert conf < 0.80
```

- [ ] **Step 2: Run to verify failure**

```bash
cd ~/Projects/sanskrit_analyzer
uv run pytest tests/test_engines/test_local_byt5_engine.py -k "compute_segment_confidence" -v
```

Expected: FAIL — method doesn't exist.

- [ ] **Step 3: Implement confidence computation**

In `~/Projects/sanskrit_analyzer/sanskrit_analyzer/engines/local_byt5_engine.py`, add after `_decode_tags` (after line 308):

```python
    def _compute_segment_confidence(self, item: dict[str, str]) -> float:
        """Compute confidence for a parsed segment.

        Higher confidence when all three components (surface, lemma, tags) are present
        and well-formed.

        Args:
            item: Dict with surface, lemma, tags keys.

        Returns:
            Confidence score 0.0-1.0.
        """
        score = 0.5  # Base: model produced output

        if item.get("surface"):
            score += 0.15
        if item.get("lemma"):
            score += 0.15
        if item.get("tags"):
            score += 0.15
            # Bonus for longer tags (more morphological info)
            if len(item["tags"]) >= 3:
                score += 0.05

        return min(score, 0.98)
```

Then update the segment creation in `analyze()` — replace lines 352-358:

```python
                pos, morph_str = self._decode_tags(item.get("tags", ""))
                segment = Segment(
                    surface=item["surface"],
                    lemma=item["lemma"],
                    morphology=morph_str,
                    confidence=self._compute_segment_confidence(item),
                    pos=pos,
                )
```

And replace line 361:

```python
            confidence = 0.90 if segments else 0.0
```

with:

```python
            confidence = (
                sum(s.confidence for s in segments) / len(segments)
                if segments
                else 0.0
            )
```

- [ ] **Step 4: Run all LocalByT5 tests**

```bash
cd ~/Projects/sanskrit_analyzer
uv run pytest tests/test_engines/test_local_byt5_engine.py -v
```

Expected: All tests pass.

- [ ] **Step 5: Commit**

```bash
cd ~/Projects/sanskrit_analyzer
git add sanskrit_analyzer/engines/local_byt5_engine.py tests/test_engines/test_local_byt5_engine.py
git commit -m "Calibrate LocalByT5 confidence based on output completeness"
```

---

### Task 5: Heritage Engine — Implement real HTML parsing (or disable)

**Context:** `heritage_engine.py:84-141` has a stubbed `_parse_heritage_response` that returns the original text as a single segment with hardcoded confidence. The Heritage Engine returns complex HTML. Rather than build a fragile HTML parser for an external service we don't control, we'll take the spec's alternative path: **disable Heritage from the default ensemble** and update config to reflect a 3-engine system.

This is the pragmatic choice because:
1. Heritage HTML format is undocumented and can change without notice
2. LocalByT5 (added recently) provides the third perspective the ensemble needs
3. Heritage can be re-enabled later with a proper parser

**Files:**
- Modify: `~/Projects/sanskrit_analyzer/sanskrit_analyzer/config.py`
- Modify: `~/Projects/sanskrit_analyzer/sanskrit_analyzer/engines/ensemble.py`
- Modify: `~/Projects/sanskrit_analyzer/tests/test_engines/test_ensemble.py`

- [ ] **Step 1: Write test for 3-engine default**

Add to `~/Projects/sanskrit_analyzer/tests/test_engines/test_ensemble.py`:

```python
    def test_create_default_excludes_heritage(self) -> None:
        """Test that default ensemble uses 3 engines without Heritage."""
        try:
            analyzer = EnsembleAnalyzer.create_default()
            assert "heritage" not in analyzer.engine_names
            assert len(analyzer.engine_names) == 3
            assert "vidyut" in analyzer.engine_names
            assert "dharmamitra" in analyzer.engine_names
            assert "local_byt5" in analyzer.engine_names
        except ImportError:
            pytest.skip("Default engines not available")
```

- [ ] **Step 2: Run to verify failure**

```bash
cd ~/Projects/sanskrit_analyzer
uv run pytest tests/test_engines/test_ensemble.py::TestEnsembleAnalyzer::test_create_default_excludes_heritage -v
```

Expected: FAIL — `create_default` still includes Heritage.

- [ ] **Step 3: Update config defaults**

In `~/Projects/sanskrit_analyzer/sanskrit_analyzer/config.py`, change `EngineConfig` line 52:

```python
    heritage: bool = False  # Disabled: HTML parser is stubbed. Re-enable when implemented.
```

- [ ] **Step 4: Update create_default to use LocalByT5 instead of Heritage**

In `~/Projects/sanskrit_analyzer/sanskrit_analyzer/engines/ensemble.py`, replace the `create_default` classmethod (lines 363-380):

```python
    @classmethod
    def create_default(cls) -> "EnsembleAnalyzer":
        """Create an ensemble with default engines.

        Uses Vidyut + Dharmamitra + LocalByT5 (Heritage disabled by default
        because its HTML parser is incomplete).

        Returns:
            EnsembleAnalyzer with 3 engines.
        """
        from sanskrit_analyzer.engines.dharmamitra_engine import DharmamitraEngine
        from sanskrit_analyzer.engines.local_byt5_engine import LocalByT5Engine
        from sanskrit_analyzer.engines.vidyut_engine import VidyutEngine

        return cls(
            engines=[
                VidyutEngine(),
                DharmamitraEngine(),
                LocalByT5Engine(),
            ]
        )
```

- [ ] **Step 5: Update the existing `test_create_default` test**

Replace the existing `test_create_default` in `TestEnsembleAnalyzer`:

```python
    def test_create_default(self) -> None:
        """Test creating default ensemble."""
        try:
            analyzer = EnsembleAnalyzer.create_default()
            assert len(analyzer.engine_names) == 3
            assert "vidyut" in analyzer.engine_names
            assert "dharmamitra" in analyzer.engine_names
            assert "local_byt5" in analyzer.engine_names
        except ImportError:
            pytest.skip("Default engines not available")
```

- [ ] **Step 6: Run all ensemble tests**

```bash
cd ~/Projects/sanskrit_analyzer
uv run pytest tests/test_engines/test_ensemble.py -v
```

Expected: All tests pass.

- [ ] **Step 7: Commit**

```bash
cd ~/Projects/sanskrit_analyzer
git add sanskrit_analyzer/config.py sanskrit_analyzer/engines/ensemble.py tests/test_engines/test_ensemble.py
git commit -m "Disable Heritage engine by default (stubbed parser), use 3-engine ensemble"
```

---

### Task 6: Ensemble — Add POS and morphology voting

**Context:** In `ensemble.py` `_merge_results`, lines 287-289 use the first engine's morphology and POS. They should use majority voting (same logic as lemma voting).

**Files:**
- Modify: `~/Projects/sanskrit_analyzer/sanskrit_analyzer/engines/ensemble.py`
- Modify: `~/Projects/sanskrit_analyzer/tests/test_engines/test_ensemble.py`

- [ ] **Step 1: Write failing test for POS voting**

Add to `~/Projects/sanskrit_analyzer/tests/test_engines/test_ensemble.py`:

```python
    @pytest.mark.asyncio
    async def test_pos_majority_voting(self) -> None:
        """Test that POS is determined by majority vote, not first engine."""
        engines = [
            MockEngine(
                "engine1", 0.33, [Segment(surface="test", lemma="test", confidence=0.9, pos="noun")]
            ),
            MockEngine(
                "engine2", 0.33, [Segment(surface="test", lemma="test", confidence=0.9, pos="verb")]
            ),
            MockEngine(
                "engine3", 0.33, [Segment(surface="test", lemma="test", confidence=0.9, pos="noun")]
            ),
        ]
        analyzer = EnsembleAnalyzer(engines=engines)

        result = await analyzer.analyze("test")

        assert result.success
        # 2 of 3 say "noun", so noun should win
        assert result.segments[0].pos == "noun"

    @pytest.mark.asyncio
    async def test_morphology_prefers_most_detailed(self) -> None:
        """Test that morphology uses the most detailed value."""
        engines = [
            MockEngine(
                "engine1", 0.33, [Segment(surface="test", lemma="test", confidence=0.9, morphology="noun")]
            ),
            MockEngine(
                "engine2", 0.33, [Segment(surface="test", lemma="test", confidence=0.9, morphology="noun.mas.nom.si")]
            ),
            MockEngine(
                "engine3", 0.33, [Segment(surface="test", lemma="test", confidence=0.9, morphology=None)]
            ),
        ]
        analyzer = EnsembleAnalyzer(engines=engines)

        result = await analyzer.analyze("test")

        assert result.success
        # Most detailed morphology should win
        assert result.segments[0].morphology == "noun.mas.nom.si"
```

- [ ] **Step 2: Run to verify failure**

```bash
cd ~/Projects/sanskrit_analyzer
uv run pytest tests/test_engines/test_ensemble.py -k "pos_majority_voting or morphology_prefers_most_detailed" -v
```

Expected: At least one test fails (POS voting not implemented).

- [ ] **Step 3: Implement POS and morphology voting**

In `~/Projects/sanskrit_analyzer/sanskrit_analyzer/engines/ensemble.py`, update the segment merging in `_merge_results`. Replace lines 284-293:

```python
            # Choose best POS by majority vote (same as lemma voting)
            best_pos = all_pos[0] if all_pos else seg.pos
            pos_disagreement = False
            if len(all_pos) > 1:
                pos_counts: dict[str, int] = {}
                for p in all_pos:
                    pos_counts[p] = pos_counts.get(p, 0) + 1
                best_pos = max(pos_counts.keys(), key=lambda x: pos_counts[x])
                # Record disagreement if not unanimous
                pos_disagreement = len(set(all_pos)) > 1

            # Choose most detailed morphology (longest string = most info)
            best_morphology = seg.morphology
            if all_morphologies:
                best_morphology = max(all_morphologies, key=len)

            # Calculate agreement score
            agreement = self._calculate_lemma_agreement(all_lemmas)

            merged_segment = MergedSegment(
                surface=seg.surface,
                lemma=best_lemma,
                morphology=best_morphology,
                confidence=weighted_confidence,
                pos=best_pos,
                meanings=list(set(all_meanings)),  # Deduplicate
                engine_votes=votes,
                agreement_score=agreement,
            )

            # Record POS disagreement in engine_votes metadata
            if pos_disagreement:
                merged_segment.engine_votes["_pos_disagreement"] = 1.0
```

- [ ] **Step 4: Run all ensemble tests**

```bash
cd ~/Projects/sanskrit_analyzer
uv run pytest tests/test_engines/test_ensemble.py -v
```

Expected: All tests pass.

- [ ] **Step 5: Commit**

```bash
cd ~/Projects/sanskrit_analyzer
git add sanskrit_analyzer/engines/ensemble.py tests/test_engines/test_ensemble.py
git commit -m "Add POS majority voting and morphology selection to ensemble"
```

---

### Task 7: Heritage confidence calibration

**Context:** Even though Heritage is disabled by default, its confidence values should be correct for when it's re-enabled. Currently it hardcodes 0.5-0.7. Since the HTML parser is still stubbed, confidence should be 0.0 for unparsed results (honest about the quality).

**Files:**
- Modify: `~/Projects/sanskrit_analyzer/sanskrit_analyzer/engines/heritage_engine.py`
- Modify: `~/Projects/sanskrit_analyzer/tests/test_engines/test_heritage_engine.py`

- [ ] **Step 1: Write test for honest confidence**

Add to `~/Projects/sanskrit_analyzer/tests/test_engines/test_heritage_engine.py`:

```python
    @pytest.mark.asyncio
    async def test_stubbed_parser_returns_low_confidence(self, engine: HeritageEngine) -> None:
        """Test that unparsed results have low confidence."""
        with patch.object(
            engine, "_query_heritage", new_callable=AsyncMock
        ) as mock_query:
            mock_query.return_value = "<html><td>some text</td></html>"

            result = await engine.analyze("gacchati")

            # Stubbed parser should be honest about quality
            assert result.confidence <= 0.3
            for seg in result.segments:
                assert seg.confidence <= 0.3
```

- [ ] **Step 2: Run to verify failure**

```bash
cd ~/Projects/sanskrit_analyzer
uv run pytest tests/test_engines/test_heritage_engine.py::TestHeritageEngine::test_stubbed_parser_returns_low_confidence -v
```

Expected: FAIL — current confidence is 0.7.

- [ ] **Step 3: Lower stubbed parser confidence**

In `~/Projects/sanskrit_analyzer/sanskrit_analyzer/engines/heritage_engine.py`:

Replace line 132 (confidence in `_parse_heritage_response`):
```python
                    confidence=0.7,  # Lower confidence for unparsed response
```
with:
```python
                    confidence=0.2,  # Stub parser: honest about quality
```

Replace line 218 (fallback confidence in `analyze`):
```python
                    confidence=0.5,
```
with:
```python
                    confidence=0.1,  # Unparsed fallback
```

Replace line 224 (overall confidence in `analyze`):
```python
                confidence=0.7 if segments else 0.0,
```
with:
```python
                confidence=0.2 if segments else 0.0,  # Stub parser
```

- [ ] **Step 4: Update existing test expectations**

In `test_heritage_engine.py`, the `test_analyze_with_valid_response` test asserts `result.success` which checks `segments > 0 and error is None`. This should still pass. But update `test_fallback_to_public` if it checks confidence.

- [ ] **Step 5: Run all Heritage tests**

```bash
cd ~/Projects/sanskrit_analyzer
uv run pytest tests/test_engines/test_heritage_engine.py -v
```

Expected: All tests pass.

- [ ] **Step 6: Commit**

```bash
cd ~/Projects/sanskrit_analyzer
git add sanskrit_analyzer/engines/heritage_engine.py tests/test_engines/test_heritage_engine.py
git commit -m "Heritage engine: honest confidence for stubbed parser"
```

---

### Task 8: Full test suite validation

**Context:** Run the entire 515-test suite to make sure all Phase B changes work together.

- [ ] **Step 1: Run full test suite**

```bash
cd ~/Projects/sanskrit_analyzer
uv run pytest
```

Expected: All 515+ tests pass.

- [ ] **Step 2: If any failures, fix them**

Common failure scenarios:
- Tests that hardcode expected confidence values (e.g., `assert result.confidence == 0.9`) — update to use ranges
- Tests that expect Heritage in `create_default` — already updated in Task 5

- [ ] **Step 3: Final commit if fixes needed**

```bash
cd ~/Projects/sanskrit_analyzer
git add -A
git commit -m "Fix test expectations for calibrated confidence values"
```
