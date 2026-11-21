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


# ---------------------------------------------------------------------------
# Weight-loading guard: the non-slow tier must never download or load weights.
# ---------------------------------------------------------------------------

# (module path, attribute path) of every entry point that loads/downloads weights.
GUARDED_ENTRY_POINTS = [
    ("transformers", "PreTrainedModel.from_pretrained"),
    ("transformers", "PreTrainedTokenizerBase.from_pretrained"),
    ("sentence_transformers", "SentenceTransformer.__init__"),
    ("huggingface_hub", "hf_hub_download"),
    ("huggingface_hub", "snapshot_download"),
    ("huggingface_hub.file_download", "hf_hub_download"),
    ("huggingface_hub._snapshot_download", "snapshot_download"),
]


def _guard_message(test_name: str, target: str) -> str:
    return (
        f"{test_name} called {target}, which loads or downloads model weights. "
        "Mark the test with @pytest.mark.slow, or mock the load."
    )


def _resolve(module_name: str, attr_path: str):
    """Return (owner, attr_name), or None if the module/attribute is absent."""
    import importlib

    try:
        owner = importlib.import_module(module_name)
    except ImportError:
        return None
    *parents, name = attr_path.split(".")
    for part in parents:
        owner = getattr(owner, part, None)
        if owner is None:
            return None
    return (owner, name) if hasattr(owner, name) else None


@pytest.fixture(autouse=True)
def _forbid_weight_loading_outside_slow(request, monkeypatch):
    if request.node.get_closest_marker("slow") is not None:
        return
    for module_name, attr_path in GUARDED_ENTRY_POINTS:
        resolved = _resolve(module_name, attr_path)
        if resolved is None:
            continue
        owner, name = resolved
        message = _guard_message(request.node.nodeid, f"{module_name}.{attr_path}")

        def _raise(*args, _message=message, **kwargs):
            raise RuntimeError(_message)

        monkeypatch.setattr(owner, name, _raise)
