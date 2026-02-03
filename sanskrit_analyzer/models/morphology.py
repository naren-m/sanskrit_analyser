"""Morphological data models for Sanskrit analysis."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


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
    gender: Optional[Gender] = None
    number: Optional[Number] = None
    case: Optional[Case] = None
    person: Optional[Person] = None
    tense: Optional[Tense] = None
    voice: Optional[Voice] = None
    raw_tag: Optional[str] = None  # Original tag string from analyzer

    def to_string(self) -> str:
        """Convert to human-readable string representation."""
        parts = [self.pos.value]
        if self.gender:
            parts.append(self.gender.value[:3])
        if self.number:
            parts.append(self.number.value[:2])
        if self.case:
            parts.append(self.case.value[:3])
        if self.person:
            parts.append(f"{self.person.value[0]}p")
        if self.tense:
            parts.append(self.tense.value[:4])
        if self.voice:
            parts.append(self.voice.value[:3])
        return ".".join(parts)

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "pos": self.pos.value if self.pos else None,
            "gender": self.gender.value if self.gender else None,
            "number": self.number.value if self.number else None,
            "case": self.case.value if self.case else None,
            "person": self.person.value if self.person else None,
            "tense": self.tense.value if self.tense else None,
            "voice": self.voice.value if self.voice else None,
            "raw_tag": self.raw_tag,
        }

    @classmethod
    def noun(
        cls,
        gender: Gender,
        number: Number,
        case: Case,
        raw_tag: Optional[str] = None,
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
        raw_tag: Optional[str] = None,
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
    meaning: Optional[str] = None  # What this pratyaya contributes
    sutra: Optional[str] = None  # Ashtadhyayi sutra reference


@dataclass(frozen=True)
class Meaning:
    """A dictionary meaning for a Sanskrit word."""

    text: str  # The meaning/definition
    language: str = "en"  # Language code (en, sa, etc.)
    source: Optional[str] = None  # Dictionary source (MW, Apte, etc.)
    confidence: float = 1.0  # Confidence in this meaning (0.0-1.0)

    def __str__(self) -> str:
        return self.text
