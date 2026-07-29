"""Utility functions for Sanskrit processing."""

from sanskrit_analyzer.utils.entity_keys import (
    canonical_key,
    fold_virama,
    is_near_spelling_variant,
    keys_match,
)
from sanskrit_analyzer.utils.normalize import detect_script, normalize_slp1

# ``is_devanagari`` is safe to surface here; the auto-detecting ``to_devanagari``/
# ``to_iast`` in ``script_routing`` deliberately shadow the explicit two-argument
# ``transliterate`` functions below, so they are NOT re-exported under those names
# — import them from ``sanskrit_analyzer.utils.script_routing`` when you want the
# auto-detecting behaviour.
from sanskrit_analyzer.utils.script_routing import is_devanagari, normalize_brahmic
from sanskrit_analyzer.utils.transliterate import (
    to_devanagari,
    to_iast,
    to_slp1,
    transliterate,
)

__all__ = [
    "transliterate",
    "to_slp1",
    "to_devanagari",
    "to_iast",
    "detect_script",
    "normalize_slp1",
    # Auto-detecting script routing + entity-key folding (#393)
    "is_devanagari",
    "normalize_brahmic",
    "canonical_key",
    "fold_virama",
    "is_near_spelling_variant",
    "keys_match",
]
