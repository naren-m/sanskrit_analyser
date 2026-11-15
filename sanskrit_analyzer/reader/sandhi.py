"""Minimal vowel sandhi for re-joining split words (6.1.77, 6.1.87-88, 6.1.101)."""
from __future__ import annotations

# Vowel sandhi at a compound-member boundary: (last of left, first of right) -> joined.
_SAVARNA = {"a": "A", "i": "I", "u": "U", "f": "F"}
_SHORT = {"A": "a", "I": "i", "U": "u", "F": "f"}
_GUNA_VRDDHI = {"i": "e", "u": "o", "f": "ar", "e": "E", "E": "E", "o": "O", "O": "O"}
_YAN = {"i": "y", "u": "v", "f": "r"}
_VOWELS = set("aAiIuUfFeEoO")


def vowel_join(left: str, right: str) -> str:
    """Join two compound members with the common vowel sandhi rules."""
    if not left or not right or left[-1] not in _VOWELS or right[0] not in _VOWELS:
        return left + right
    x, y = _SHORT.get(left[-1], left[-1]), _SHORT.get(right[0], right[0])
    head, tail = left[:-1], right[1:]
    if x == y and x in _SAVARNA:            # 6.1.101 akaH savarRe dIrghaH
        return head + _SAVARNA[x] + tail
    if x == "a" and y in _GUNA_VRDDHI:       # 6.1.87 Ad guRaH, 6.1.88 vfdDir eci
        return head + _GUNA_VRDDHI[y] + tail
    if x in _YAN:                            # 6.1.77 iko yaR aci
        return head + _YAN[x] + right
    return left + right
