"""Session-wide guards that run before any test is collected.

Currently one guard: refuse to run at all when a plugin the suite depends on is
missing, rather than letting the run degrade into a pile of meaningless
failures.
"""

from __future__ import annotations

import pytest

_MISSING_ASYNCIO = """\
pytest-asyncio is not installed in this interpreter.

The suite sets `asyncio_mode = "auto"` and a large part of it is async, so
without the plugin every async test is collected, never awaited, and reported
as a bare FAILED with no traceback — around 110 of them. That looks exactly
like a broken codebase and is not one.

The usual cause is running with a sibling project's virtualenv. Use this
project's own environment:

    ./.venv/bin/python -m pytest tests/ -q

or install the dev extras into the interpreter you are using:

    python -m pip install -e '.[dev]'
"""


def pytest_configure(config: pytest.Config) -> None:
    """Abort the session when pytest-asyncio is absent.

    A ``UsageError`` prints the message and stops before collection, so the
    real problem is the only thing on screen.

    This deliberately does not use ``--strict-config`` in ``addopts``: pytest
    validates ini keys while it loads the ini file, so a flag supplied from
    ``addopts`` arrives too late and ``asyncio_mode`` is still only a warning.
    """
    if config.pluginmanager.hasplugin("asyncio"):
        return
    raise pytest.UsageError(_MISSING_ASYNCIO)
