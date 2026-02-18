# Workflow Conventions

## Code Simplification Rule

**After completing EVERY task, run the code-simplifier agent.**

Workflow:
1. Complete the task
2. Run `code-simplifier:code-simplifier` agent on affected files
3. Verify all tests pass
4. Commit changes

This keeps the codebase simple and maintainable.
