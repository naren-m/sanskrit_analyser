"""Table-driven test helper (test policy rule 2).

One test function owns one behaviour cluster; its inputs live in a ``CASES``
table. ``check_cases`` runs every row, collects every failure, and fails once
with all of them, so one bad row never hides the next.

Row shapes:

- a tuple ``(row_id, *args)``: ``check(*args)`` is called;
- a dict with an ``"id"`` key (JSON gold files): ``check(row)`` is called.

The row id says what the case proves; it is what a failure report names.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
from typing import Any

import pytest


def _split(row: Any) -> tuple[str, tuple[Any, ...]]:
    if isinstance(row, Mapping):
        return str(row["id"]), (row,)
    return str(row[0]), tuple(row[1:])


def check_cases(
    cases: Iterable[Any],
    check: Callable[..., Any],
    *,
    xfail: Mapping[str, str] | None = None,
) -> None:
    """Run ``check`` on every row and report all failures together.

    ``xfail`` maps a row id to the reason it is a known gap. Known gaps are
    strict: the row must fail, and a row that starts passing is reported so the
    entry gets deleted. A row that calls ``pytest.skip`` is skipped on its own;
    if every row skips, the whole test is reported as skipped rather than
    passing vacuously.
    """
    rows = [_split(row) for row in cases]
    assert rows, "empty CASES table"
    ids = [row_id for row_id, _ in rows]
    dupes = sorted({i for i in ids if ids.count(i) > 1})
    assert not dupes, f"duplicate row ids: {dupes}"
    gaps = dict(xfail or {})
    stale = sorted(set(gaps) - set(ids))
    assert not stale, f"xfail ids with no matching row: {stale}"

    failures: list[str] = []
    skipped: list[str] = []
    for row_id, args in rows:
        try:
            check(*args)
        except pytest.skip.Exception as exc:
            skipped.append(f"[{row_id}] {exc}")
            continue
        except Exception as exc:  # noqa: BLE001 - every row's error is reported
            if row_id not in gaps:
                failures.append(f"[{row_id}] {type(exc).__name__}: {exc}")
        else:
            if row_id in gaps:
                failures.append(f"[{row_id}] XPASS (strict): {gaps[row_id]}")
    if len(skipped) == len(rows):
        pytest.skip("every case skipped: " + "; ".join(skipped))
    if failures:
        pytest.fail(
            f"{len(failures)} of {len(rows)} cases failed:\n" + "\n".join(failures),
            pytrace=False,
        )
