# Sanskrit Analyzer - Project Instructions

## Mandatory Workflow

**After completing EVERY task, run the code-simplifier agent:**

```
Task tool with subagent_type="code-simplifier:code-simplifier"
```

This is non-negotiable. The codebase must stay simple.

## Testing

Always run tests after changes:
```bash
uv run pytest
```

The full suite (~900 tests) must pass before committing. Everything runs
offline; tests that need ML model weights are marked `slow` and skip when the
weights are absent.
