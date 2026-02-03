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

All 380 tests must pass before committing.
