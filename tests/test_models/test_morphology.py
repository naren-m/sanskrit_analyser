"""Tests for MorphologicalTag serialization robustness (issue #349).

The dataclass field annotations (``pos: PartOfSpeech`` …) are type hints, not
runtime constraints.  An upstream analyzer may populate a field with a plain
``str`` instead of the enum member; serialization must not crash in that case.
"""

from __future__ import annotations

from sanskrit_analyzer.models.morphology import (
    Case,
    Gender,
    MorphologicalTag,
    Number,
    PartOfSpeech,
    _tag_value,
)
from tests._cases import check_cases

ENUM_NOUN = MorphologicalTag(
    pos=PartOfSpeech.NOUN,
    gender=Gender.MASCULINE,
    number=Number.SINGULAR,
    case=Case.NOMINATIVE,
)
ALL_STR = MorphologicalTag(
    pos="verb",  # type: ignore[arg-type]
    gender="masculine",  # type: ignore[arg-type]
    number="singular",  # type: ignore[arg-type]
    case="nominative",  # type: ignore[arg-type]
    person="third",  # type: ignore[arg-type]
    tense="present",  # type: ignore[arg-type]
    voice="active",  # type: ignore[arg-type]
)


def test_tag_value_normalizes_enum_str_none() -> None:
    cases = [
        ("enum_to_value", PartOfSpeech.NOUN, "noun"),
        ("plain_str_passes_through", "noun", "noun"),
        ("none_stays_none", None, None),
    ]

    def check(value, expected):
        assert _tag_value(value) == expected

    check_cases(cases, check)


# (id, tag, expected subset of to_dict())
TO_DICT_CASES = [
    ("enum_fields", ENUM_NOUN, {
        "pos": "noun", "gender": "masculine", "number": "singular",
        "case": "nominative", "person": None,
    }),
    ("issue_349_str_pos_does_not_crash", MorphologicalTag(pos="noun"),  # type: ignore[arg-type]
     {"pos": "noun"}),
    ("issue_349_every_field_str", ALL_STR, {
        "pos": "verb", "gender": "masculine", "number": "singular", "case": "nominative",
        "person": "third", "tense": "present", "voice": "active", "raw_tag": None,
    }),
]


def test_to_dict() -> None:
    def check(tag, expected):
        d = tag.to_dict()
        assert {k: d[k] for k in expected} == expected, d

    check_cases(TO_DICT_CASES, check)
    # The all-str row is the full dict, not a subset: no stray keys.
    assert ALL_STR.to_dict() == TO_DICT_CASES[2][2]


def test_to_string() -> None:
    cases = [
        ("enum_fields", ENUM_NOUN, "noun.mas.si.nom"),
        # pos + gender[:3]
        ("issue_349_str_fields_do_not_crash",
         MorphologicalTag(pos="noun", gender="masculine"),  # type: ignore[arg-type]
         "noun.mas"),
    ]

    def check(tag, expected):
        assert tag.to_string() == expected

    check_cases(cases, check)
