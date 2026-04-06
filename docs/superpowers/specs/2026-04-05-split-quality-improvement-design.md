# Split Quality Improvement: Vocabulary-Validated Re-scoring

## Problem

Vidyut's cheda module produces poor sandhi splits for many Yoga Sutra compounds:

| Input | Current Split | Expected Split |
|-------|--------------|----------------|
| yogasutra | yogas + ut + ra | yoga + sutra |
| yogānuśāsanam | yogān + uśā + asanam | yoga + anuśāsanam |
| atha | at + ha | atha (indeclinable) |
| yogaścittavṛttinirodhaḥ | (unsplit) | yoga + citta + vṛtti + nirodha |

Root causes:
- Vidyut makes incorrect sandhi boundary decisions on compounds not well-represented in its training data
- No validation that produced segments are real Sanskrit words
- No protection for indeclinables (words that should never be split)
- No fallback when splits produce nonsense tokens

## Scope

Primary use case: word-by-word reading in Yoga Sutras. Users click a word in a sutra and see it broken into meaningful components. The ~196 sutras define the vocabulary that must split correctly.

## Design

### Architecture

A new `SplitValidator` module sits between Vidyut's raw output and the tree builder:

```
Input text
  |
VidyutEngine.analyze()  ->  raw segments (may be bad)
  |
SplitValidator.validate_and_rescore()
  |-- Generate candidate splits (alternative boundary positions)
  |-- Score each candidate against YogaSutraVocabulary
  |-- Protect indeclinables from splitting
  |-- Return best-scoring candidate
  |
TreeBuilder.build()  ->  AnalysisTree
```

### New Files

| File | Purpose |
|------|---------|
| `sanskrit_analyzer/validation/__init__.py` | Package init |
| `sanskrit_analyzer/validation/split_validator.py` | Candidate generation + scoring logic |
| `sanskrit_analyzer/validation/vocabulary.py` | Loads and queries the curated vocabulary |
| `sanskrit_analyzer/data/yoga_sutra_vocabulary.json` | Curated word list (~200-400 lemmas) |
| `tests/data/yoga_sutra_splits_golden.json` | Golden test file with ~20 compounds and expected splits |
| `tests/test_split_validator.py` | Unit tests for the validator |
| `tests/test_golden_splits.py` | Golden split tests using real Analyzer |

### Modified Files

| File | Change |
|------|--------|
| `sanskrit_analyzer/analyzer.py` | Wire SplitValidator after engine results, before tree building |
| `sanskrit_analyzer/engines/vidyut_engine.py` | Expose raw token data for candidate generation |

### Candidate Generation

When Vidyut produces segments, the validator generates alternative split candidates using sliding boundary recombination:

1. Take Vidyut's segments and the original SLP1 string
2. Generate candidates by:
   - **Merging adjacent segments** — Combine pairs and triples to produce longer chunks
   - **Re-splitting merged chunks** — For each merged chunk, try splitting at every character position and check if both halves score well against the vocabulary
   - **Preserving Vidyut's original** — Always include it as a candidate
3. **Handling unsplit compounds** — When Vidyut returns a single unsplit token (e.g., `yogaścittavṛttinirodhaḥ`), generate candidates by trying all split positions on the full string and recursively splitting the resulting chunks. Use the vocabulary to prune: only keep splits where at least one half matches a known word.
4. Cap candidate count at ~20 to prevent combinatorial blowup

Example for `yogasutra` (SLP1):
```
Vidyut says:     yogas | ut | ra        (3 segments)
Candidates:
  1. yogas | ut | ra                    (original)
  2. yogasutra                          (fully merged, unsplit)
  3. yoga | sutra                       (re-split merged at position 4)
  4. yogas | utra                       (merge last two)
  5. yogasut | ra                       (merge first two)
```

### Scoring Function

Each candidate split gets a score:

| Signal | Score |
|--------|-------|
| Segment lemma found in vocabulary | +2.0 |
| Segment is a known indeclinable | +3.0 (also prevents further splitting) |
| Segment has valid morphological data from Vidyut | +1.0 |
| Segment is a single character | -2.0 |
| Segment lemma not found anywhere | -1.0 |
| Fewer total segments (simplicity bonus) | +0.5 per reduction vs max candidate |

Final score = sum of segment scores. Highest wins. Ties favor fewer segments.

### Vocabulary File

`sanskrit_analyzer/data/yoga_sutra_vocabulary.json`:

```json
{
  "version": "1.0",
  "description": "Curated vocabulary from the 196 Yoga Sutras of Patanjali",
  "words": [
    {"lemma": "yoga", "slp1": "yoga", "type": "noun", "indeclinable": false},
    {"lemma": "atha", "slp1": "aTa", "type": "indeclinable", "indeclinable": true},
    {"lemma": "sutra", "slp1": "sUtra", "type": "noun", "indeclinable": false},
    {"lemma": "citta", "slp1": "citta", "type": "noun", "indeclinable": false},
    {"lemma": "vrtti", "slp1": "vftti", "type": "noun", "indeclinable": false},
    {"lemma": "nirodha", "slp1": "niroDa", "type": "noun", "indeclinable": false}
  ]
}
```

Built by extracting unique lemmas from the 196 sutras' word_analysis data, plus common Sanskrit grammatical words (pronouns, particles, conjunctions). Roughly 200-400 entries.

### Indeclinable Protection

Words marked `indeclinable: true` in the vocabulary (e.g., `atha`, `iti`, `ca`, `tu`, `eva`, `tatra`) receive special handling:

- Before candidate generation, check if the entire input matches an indeclinable
- If so, return it unsplit with a +3.0 score bonus
- This prevents `atha` from being split into `at + ha`

### Integration Point

In `analyzer.py`, after engine analysis and before tree building:

```python
# After engine results
engine_result = await self._engine.analyze(text)

# Validate and re-score splits
validator = SplitValidator(vocabulary)
validated_segments = validator.validate_and_rescore(
    engine_result.segments,
    normalized_slp1
)

# Build tree from validated segments
tree = self._tree_builder.build_from_segments(validated_segments, ...)
```

Non-breaking: if the validator has no vocabulary loaded or finds no better candidate, it passes through the original segments unchanged.

## Testing

### Golden Test File

`tests/data/yoga_sutra_splits_golden.json` with ~20 compounds:

```json
[
  {"input": "yogānuśāsanam", "expected_lemmas": ["yoga", "anuśāsana"]},
  {"input": "yogaścittavṛttinirodhaḥ", "expected_lemmas": ["yoga", "citta", "vṛtti", "nirodha"]},
  {"input": "atha", "expected_lemmas": ["atha"]},
  {"input": "abhyāsavairāgyābhyām", "expected_lemmas": ["abhyāsa", "vairāgya"]},
  {"input": "yogasutra", "expected_lemmas": ["yoga", "sūtra"]},
  {"input": "tadā", "expected_lemmas": ["tadā"]},
  {"input": "vṛttisārūpyam", "expected_lemmas": ["vṛtti", "sārūpya"]},
  {"input": "draṣṭuḥ", "expected_lemmas": ["draṣṭṛ"]},
  {"input": "svarūpe", "expected_lemmas": ["svarūpa"]},
  {"input": "pramāṇaviparyayavikalpanidrāsmṛtayaḥ", "expected_lemmas": ["pramāṇa", "viparyaya", "vikalpa", "nidrā", "smṛti"]}
]
```

### Test Strategy

- `test_split_validator.py`: Unit tests for candidate generation, scoring, indeclinable protection
- `test_golden_splits.py`: Integration tests using real Analyzer, asserting top-scoring candidate matches expected lemmas
- All existing 380 tests must continue to pass
- Run with: `uv run pytest`

## Updating Yoga Sutras

After the `sanskrit_analyzer` improvement:
- Bump the `sanskrit_analyzer` dependency version in `yoga_sutras/backend/requirements.txt`
- No adapter code changes needed — the improvement is transparent to consumers

## Success Criteria

- All ~20 golden test compounds split correctly
- `atha` stays as `atha` (not `at + ha`)
- `yogasutra` splits as `yoga + sutra` (not `yogas + ut + ra`)
- `yogānuśāsanam` splits as `yoga + anuśāsanam`
- No regression on existing 380 tests
- Latency increase < 50ms per split (candidate generation is bounded)
