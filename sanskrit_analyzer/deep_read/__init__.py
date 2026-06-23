"""Deep Read: a Sanskrit line -> per-pada dhātu analyses.

A reusable, scripture-agnostic facility promoted out of ramayanam. The public
entry point is :class:`DeepRead`; results are the typed :class:`DeepReadResult`
model whose ``.to_dict()`` reproduces the legacy plain-dict shape consumers rely
on.

The kosha engine's transliteration helpers (:func:`kosha_engine.slp`,
:func:`~kosha_engine.to_iast`, :func:`~kosha_engine.to_devanagari`) are public
and importable from :mod:`sanskrit_analyzer.deep_read.kosha_engine`.
"""

from sanskrit_analyzer.deep_read.facade import DeepRead
from sanskrit_analyzer.deep_read.models import (
    Analysis,
    DeepReadResult,
    DhatuBlock,
    Token,
)

__all__ = [
    "DeepRead",
    "DeepReadResult",
    "Token",
    "Analysis",
    "DhatuBlock",
]
