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


class TestTagValueHelper:
    """`_tag_value` normalizes enum / str / None uniformly."""

    def test_enum_returns_value(self):
        assert _tag_value(PartOfSpeech.NOUN) == "noun"

    def test_plain_str_passes_through(self):
        assert _tag_value("noun") == "noun"

    def test_none_returns_none(self):
        assert _tag_value(None) is None


class TestToDictWithEnums:
    """Canonical (enum-typed) tag serializes as before."""

    def test_to_dict_enum_pos(self):
        tag = MorphologicalTag(
            pos=PartOfSpeech.NOUN,
            gender=Gender.MASCULINE,
            number=Number.SINGULAR,
            case=Case.NOMINATIVE,
        )
        d = tag.to_dict()
        assert d["pos"] == "noun"
        assert d["gender"] == "masculine"
        assert d["number"] == "singular"
        assert d["case"] == "nominative"
        assert d["person"] is None


class TestToDictWithPlainStrings:
    """A str in an enum field must not raise (the #349 crash)."""

    def test_to_dict_str_pos_does_not_crash(self):
        tag = MorphologicalTag(pos="noun")  # type: ignore[arg-type]
        d = tag.to_dict()
        assert d["pos"] == "noun"

    def test_to_dict_all_fields_as_str(self):
        tag = MorphologicalTag(
            pos="verb",  # type: ignore[arg-type]
            gender="masculine",  # type: ignore[arg-type]
            number="singular",  # type: ignore[arg-type]
            case="nominative",  # type: ignore[arg-type]
            person="third",  # type: ignore[arg-type]
            tense="present",  # type: ignore[arg-type]
            voice="active",  # type: ignore[arg-type]
        )
        d = tag.to_dict()
        assert d == {
            "pos": "verb",
            "gender": "masculine",
            "number": "singular",
            "case": "nominative",
            "person": "third",
            "tense": "present",
            "voice": "active",
            "raw_tag": None,
        }


class TestToString:
    """`to_string` is equally robust to str fields."""

    def test_to_string_enum(self):
        tag = MorphologicalTag(
            pos=PartOfSpeech.NOUN,
            gender=Gender.MASCULINE,
            number=Number.SINGULAR,
            case=Case.NOMINATIVE,
        )
        assert tag.to_string() == "noun.mas.si.nom"

    def test_to_string_str_pos_does_not_crash(self):
        tag = MorphologicalTag(
            pos="noun",  # type: ignore[arg-type]
            gender="masculine",  # type: ignore[arg-type]
        )
        # pos + gender[:3]
        assert tag.to_string() == "noun.mas"
