"""``dhatu`` and ``prakriya`` are independent paths; they share only ``vidyut_data``/``utils``."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

PKG = Path(__file__).resolve().parents[1] / "sanskrit_analyzer"

FORBIDDEN = {
    "dhatu": ("sanskrit_analyzer.prakriya",),
    "prakriya": ("sanskrit_analyzer.dhatu", "sanskrit_analyzer.deep_read"),
}


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found.update(a.name for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            found.add(node.module)
    return found


@pytest.mark.parametrize("package,forbidden", FORBIDDEN.items())
def test_package_does_not_import(package, forbidden):
    offenders = []
    for path in (PKG / package).rglob("*.py"):
        for mod in _imports(path):
            if mod.startswith(forbidden):
                offenders.append(f"{path.relative_to(PKG)} -> {mod}")
    assert not offenders, "\n".join(offenders)
