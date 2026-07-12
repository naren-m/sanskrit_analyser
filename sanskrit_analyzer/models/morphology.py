"""Morphological data models for Sanskrit analysis."""

from dataclasses import dataclass, field
from enum import Enum


def _tag_value(value):
    """Normalize a morphology field to its serialized value.

    Field annotations on :class:`MorphologicalTag` (``pos: PartOfSpeech`` …) are
    type hints, not runtime constraints, so an upstream analyzer can populate a
    field with a plain ``str`` instead of the enum member.  Accessing ``.value``
    on such a value would raise ``AttributeError`` (issue #349).  This helper
    returns ``.value`` for enum members and passes ``str``/``None`` through
    unchanged, so serialization is robust to either representation.
    """
    if value is None:
        return None
    return value.value if isinstance(value, Enum) else value


class PartOfSpeech(Enum):
    """Part of speech classification."""

    NOUN = "noun"
    VERB = "verb"
    ADJECTIVE = "adjective"
    ADVERB = "adverb"
    PRONOUN = "pronoun"
    INDECLINABLE = "indeclinable"  # avyaya
    PARTICIPLE = "participle"
    INFINITIVE = "infinitive"
    GERUND = "gerund"
    PREFIX = "prefix"  # upasarga
    PARTICLE = "particle"


class Gender(Enum):
    """Grammatical gender."""

    MASCULINE = "masculine"
    FEMININE = "feminine"
    NEUTER = "neuter"


class Number(Enum):
    """Grammatical number."""

    SINGULAR = "singular"
    DUAL = "dual"
    PLURAL = "plural"


class Case(Enum):
    """Sanskrit cases (vibhakti)."""

    NOMINATIVE = "nominative"  # prathamā
    ACCUSATIVE = "accusative"  # dvitīyā
    INSTRUMENTAL = "instrumental"  # tṛtīyā
    DATIVE = "dative"  # caturthī
    ABLATIVE = "ablative"  # pañcamī
    GENITIVE = "genitive"  # ṣaṣṭhī
    LOCATIVE = "locative"  # saptamī
    VOCATIVE = "vocative"  # sambodhana


class Person(Enum):
    """Grammatical person for verbs."""

    FIRST = "first"
    SECOND = "second"
    THIRD = "third"


class Tense(Enum):
    """Sanskrit tenses and moods (lakāra)."""

    PRESENT = "present"  # laṭ
    IMPERFECT = "imperfect"  # laṅ
    IMPERATIVE = "imperative"  # loṭ
    POTENTIAL = "potential"  # liṅ (vidhi)
    PERFECT = "perfect"  # liṭ
    AORIST = "aorist"  # luṅ
    FUTURE = "future"  # lṛṭ
    CONDITIONAL = "conditional"  # lṛṅ
    BENEDICTIVE = "benedictive"  # āśīrliṅ
    PERIPHRASTIC_FUTURE = "periphrastic_future"  # luṭ


class Voice(Enum):
    """Grammatical voice."""

    ACTIVE = "active"  # parasmaipada
    MIDDLE = "middle"  # ātmanepada
    PASSIVE = "passive"


class SandhiType(Enum):
    """Types of sandhi (phonetic combination)."""

    SAVARNA_DIRGHA = "savarṇa-dīrgha"  # Similar vowels merge to long
    GUNA = "guṇa"  # a/ā + i/ī → e, a/ā + u/ū → o
    VRDDHI = "vṛddhi"  # a/ā + e/ai → ai, a/ā + o/au → au
    YAN = "yāṇ"  # i/ī → y, u/ū → v before vowel
    VISARGA = "visarga"  # ḥ transformations
    CONSONANT = "consonant"  # Consonant sandhi
    ANUSVARA = "anusvāra"  # m → ṃ before consonant
    NONE = "none"  # No sandhi applied


@dataclass(frozen=True)
class MorphologicalTag:
    """Complete morphological analysis tag for a word.

    This captures the full grammatical information for a Sanskrit word.
    """

    pos: PartOfSpeech
    gender: Gender | None = None
    number: Number | None = None
    case: Case | None = None
    person: Person | None = None
    tense: Tense | None = None
    voice: Voice | None = None
    raw_tag: str | None = None  # Original tag string from analyzer

    def to_string(self) -> str:
        """Convert to human-readable string representation."""
        parts = [_tag_value(self.pos) or ""]
        if self.gender:
            parts.append(_tag_value(self.gender)[:3])
        if self.number:
            parts.append(_tag_value(self.number)[:2])
        if self.case:
            parts.append(_tag_value(self.case)[:3])
        if self.person:
            parts.append(f"{_tag_value(self.person)[0]}p")
        if self.tense:
            parts.append(_tag_value(self.tense)[:4])
        if self.voice:
            parts.append(_tag_value(self.voice)[:3])
        return ".".join(parts)

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "pos": _tag_value(self.pos),
            "gender": _tag_value(self.gender),
            "number": _tag_value(self.number),
            "case": _tag_value(self.case),
            "person": _tag_value(self.person),
            "tense": _tag_value(self.tense),
            "voice": _tag_value(self.voice),
            "raw_tag": self.raw_tag,
        }

    @classmethod
    def noun(
        cls,
        gender: Gender,
        number: Number,
        case: Case,
        raw_tag: str | None = None,
    ) -> "MorphologicalTag":
        """Create a noun morphological tag."""
        return cls(
            pos=PartOfSpeech.NOUN,
            gender=gender,
            number=number,
            case=case,
            raw_tag=raw_tag,
        )

    @classmethod
    def verb(
        cls,
        person: Person,
        number: Number,
        tense: Tense,
        voice: Voice = Voice.ACTIVE,
        raw_tag: str | None = None,
    ) -> "MorphologicalTag":
        """Create a verb morphological tag."""
        return cls(
            pos=PartOfSpeech.VERB,
            person=person,
            number=number,
            tense=tense,
            voice=voice,
            raw_tag=raw_tag,
        )


@dataclass(frozen=True)
class Pratyaya:
    """A grammatical suffix (pratyaya) applied to a stem.

    Pratyayas are affixes that transform stems into inflected forms.
    """

    name: str  # The pratyaya name (e.g., "kvip", "kyap", "ṇic")
    type: str  # Category: "kṛt", "taddhita", "tiṅ", "sup"
    meaning: str | None = None  # What this pratyaya contributes
    sutra: str | None = None  # Ashtadhyayi sutra reference


@dataclass(frozen=True)
class Meaning:
    """A dictionary meaning for a Sanskrit word."""

    text: str  # The meaning/definition
    language: str = "en"  # Language code (en, sa, etc.)
    source: str | None = None  # Dictionary source (MW, Apte, etc.)
    confidence: float = 1.0  # Confidence in this meaning (0.0-1.0)

    def __str__(self) -> str:
        return self.text
