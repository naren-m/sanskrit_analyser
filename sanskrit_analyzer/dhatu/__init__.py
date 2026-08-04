"""Local, offline generic dhātu identifier (Dharmamitra-free).

Public surface:

* :class:`~sanskrit_analyzer.dhatu.identifier.DhatuIdentifier` — segment a line
  and identify each pada's verbal root.
* :func:`~sanskrit_analyzer.dhatu.segmenter.segment` — the sandhi-aware DP
  segmenter (drop-in for the old remote ``segment`` contract).
"""

from sanskrit_analyzer.dhatu.dhatupatha import DhatuKosha, strip_anubandhas
from sanskrit_analyzer.dhatu.identifier import DhatuIdentifier, TokenResult, rank_analyses
from sanskrit_analyzer.dhatu.resolver import DhatuResolver, get_dhatu_resolver
from sanskrit_analyzer.dhatu.segmenter import segment

__all__ = [
    "DhatuIdentifier",
    "DhatuKosha",
    "DhatuResolver",
    "TokenResult",
    "get_dhatu_resolver",
    "rank_analyses",
    "segment",
    "strip_anubandhas",
]
