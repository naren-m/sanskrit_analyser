"""The curated lexical category sets keep their shape and key form."""

from __future__ import annotations

import pytest

from sanskrit_analyzer.lexical_categories import (
    GENERIC_EPITHET_KEYS,
    PRONOUN_KEYS,
    ROLE_NOUN_KEYS,
)

SETS = {
    "role": ROLE_NOUN_KEYS,
    "pronoun": PRONOUN_KEYS,
    "epithet": GENERIC_EPITHET_KEYS,
}


@pytest.mark.parametrize("name", SETS)
def test_set_is_nonempty_frozenset_of_str(name: str) -> None:
    keys = SETS[name]
    assert isinstance(keys, frozenset)
    assert keys
    assert all(isinstance(k, str) for k in keys)


@pytest.mark.parametrize(
    ("name", "key", "present"),
    [
        ("role", "vira", True),
        ("role", "putra", True),
        ("role", "janaka", False),  # a person, deliberately absent
        ("role", "वीर", False),  # keys are romanised, not Devanagari
        ("pronoun", "aham", True),
        ("pronoun", "tvam", True),
        ("pronoun", "ka", False),  # a name of Prajapati, deliberately absent
        ("pronoun", "atman", False),
        ("epithet", "dharmatma", True),
        ("epithet", "munivara", True),
    ],
)
def test_key_form(name: str, key: str, present: bool) -> None:
    assert (key in SETS[name]) is present


@pytest.mark.parametrize(
    ("a", "b", "overlap"),
    [
        ("role", "pronoun", set()),
        ("pronoun", "epithet", set()),
        ("role", "epithet", {"vira", "rajan", "prabhu", "deva", "mahatman"}),
    ],
)
def test_pairwise_overlap_is_pinned(a: str, b: str, overlap: set[str]) -> None:
    assert SETS[a] & SETS[b] == overlap
