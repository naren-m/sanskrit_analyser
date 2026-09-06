"""Locate and load the vidyut data bundle, once per process.

Every package that touches vidyut (``dhatu``, ``deep_read``, ``prakriya``,
``validation``, ``engines``) goes through here, so they all agree on which
bundle is in use and share one ``Kosha`` instance. ``dhatu`` and ``prakriya``
must not import each other; this module is the only thing they share.
"""
from __future__ import annotations

import logging
import os
from functools import lru_cache
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class VidyutUnavailable(RuntimeError):  # noqa: N818 - name is downstream API
    """Raised when the vidyut data bundle cannot be located/loaded."""


def resolve_data_dir() -> Path | None:
    """Find a vidyut data directory that actually contains a ``kosha`` subdir.

    Order: ``VIDYUT_DATA_DIR`` env, a ``vidyut-0.4.0/`` bundle in the current
    working directory (a consuming project run from its repo root — e.g.
    ramayanam's ``python run.py`` — ships the bundle there), then the
    user-level ``~/.vidyut-data``. The bundle path is *data*, not a secret, so a
    default search is fine.

    This is deliberately layout-agnostic: as a shared library module we cannot
    assume any fixed depth relative to a host repo, so discovery is driven by an
    explicit env var and well-known locations rather than ``__file__`` arithmetic.
    """
    candidates: list[Path] = []
    env = os.environ.get("VIDYUT_DATA_DIR")
    if env:
        candidates.append(Path(env).expanduser())
    candidates.append(Path.cwd() / "vidyut-0.4.0")
    candidates.append(Path.home() / ".vidyut-data")

    for c in candidates:
        if (c / "kosha").is_dir():
            return c
    return None


def is_available() -> bool:
    """True if the vidyut data bundle is present (does not load the kosha)."""
    return resolve_data_dir() is not None


@lru_cache(maxsize=1)
def kosha() -> Any:
    """The process-wide ``vidyut.kosha.Kosha``; raises if the bundle is missing."""
    data_dir = resolve_data_dir()
    if data_dir is None:
        raise VidyutUnavailable(
            "vidyut data bundle not found. Checked VIDYUT_DATA_DIR, "
            "<cwd>/vidyut-0.4.0, and ~/.vidyut-data."
        )
    from vidyut.kosha import Kosha  # imported lazily so import-time stays cheap

    logger.info("Loading vidyut kosha from %s", data_dir / "kosha")
    return Kosha(str(data_dir / "kosha"))
