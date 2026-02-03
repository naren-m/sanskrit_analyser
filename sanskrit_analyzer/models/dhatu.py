"""Dhatu (verbal root) data models for Sanskrit analysis."""

from dataclasses import dataclass, field
from typing import Optional

from sanskrit_analyzer.models.scripts import ScriptVariants


class Gana:
    """Sanskrit verb classes (gaṇa).

    The 10 verb classes determine how dhatus are conjugated.
    """

    BHVADI = 1  # bhū-ādi (भ्वादि)
    ADADI = 2  # ad-ādi (अदादि)
    JUHOTYADI = 3  # juhotyādi (जुहोत्यादि)
    DIVADI = 4  # div-ādi (दिवादि)
    SVADI = 5  # su-ādi (स्वादि)
    TUDADI = 6  # tud-ādi (तुदादि)
    RUDHADI = 7  # rudh-ādi (रुधादि)
    TANADI = 8  # tan-ādi (तनादि)
    KRYADI = 9  # krī-ādi (क्र्यादि)
    CURADI = 10  # cur-ādi (चुरादि)

    @classmethod
    def name(cls, gana: int) -> str:
        """Get the name of a gana."""
        names = {
            1: "bhvādi",
            2: "adādi",
            3: "juhotyādi",
            4: "divādi",
            5: "svādi",
            6: "tudādi",
            7: "rudhādi",
            8: "tanādi",
            9: "kryādi",
            10: "curādi",
        }
        return names.get(gana, f"gaṇa-{gana}")


class Pada:
    """Voice/pada classification for dhatus."""

    PARASMAIPADA = "parasmaipada"  # Active endings
    ATMANEPADA = "ātmanepada"  # Middle endings
    UBHAYAPADA = "ubhayapada"  # Both


@dataclass(frozen=True)
class DhatuInfo:
    """Complete information about a Sanskrit verbal root (dhātu).

    A dhatu is the root form of a verb from which all verbal forms derive.
    """

    dhatu: str  # The root form in SLP1 (e.g., "gam", "kf", "BU")
    scripts: ScriptVariants  # The dhatu in all scripts
    gana: int  # Verb class (1-10)
    pada: str  # parasmaipada, ātmanepada, or ubhayapada
    meanings: list[str] = field(default_factory=list)  # Primary meanings
    prakriya: Optional[list[str]] = None  # Derivation steps (if available)
    sutra: Optional[str] = None  # Dhātupāṭha reference
    index: Optional[int] = None  # Index in Dhātupāṭha

    @property
    def gana_name(self) -> str:
        """Get the name of this dhatu's gana."""
        return Gana.name(self.gana)

    @property
    def primary_meaning(self) -> Optional[str]:
        """Get the primary meaning of this dhatu."""
        return self.meanings[0] if self.meanings else None

    def __str__(self) -> str:
        """Return string representation."""
        meaning = self.primary_meaning or "?"
        return f"√{self.scripts.iast} ({self.gana_name}): {meaning}"

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "dhatu": self.dhatu,
            "meaning": self.primary_meaning,
            "gana": self.gana,
            "pada": self.pada,
            "meanings": self.meanings,
        }

    @classmethod
    def create(
        cls,
        dhatu_slp1: str,
        gana: int,
        pada: str,
        meanings: list[str],
        prakriya: Optional[list[str]] = None,
    ) -> "DhatuInfo":
        """Create a DhatuInfo from SLP1 dhatu string.

        Args:
            dhatu_slp1: The dhatu in SLP1 script.
            gana: The verb class (1-10).
            pada: The pada classification.
            meanings: List of meanings.
            prakriya: Optional derivation steps.

        Returns:
            A new DhatuInfo instance.
        """
        from sanskrit_analyzer.models.scripts import Script, ScriptVariants

        scripts = ScriptVariants.from_text(dhatu_slp1, Script.SLP1)
        return cls(
            dhatu=dhatu_slp1,
            scripts=scripts,
            gana=gana,
            pada=pada,
            meanings=meanings,
            prakriya=prakriya,
        )


# Common dhatus for reference
COMMON_DHATUS = {
    "gam": DhatuInfo.create("gam", 1, Pada.PARASMAIPADA, ["to go"]),
    "kf": DhatuInfo.create("kf", 8, Pada.UBHAYAPADA, ["to do", "to make"]),
    "BU": DhatuInfo.create("BU", 1, Pada.PARASMAIPADA, ["to be", "to become"]),
    "as": DhatuInfo.create("as", 2, Pada.PARASMAIPADA, ["to be"]),
    "vac": DhatuInfo.create("vac", 2, Pada.PARASMAIPADA, ["to speak"]),
    "dfS": DhatuInfo.create("dfS", 1, Pada.PARASMAIPADA, ["to see"]),
    "Sru": DhatuInfo.create("Sru", 5, Pada.PARASMAIPADA, ["to hear"]),
    "DA": DhatuInfo.create("DA", 3, Pada.UBHAYAPADA, ["to place", "to hold"]),
    "dA": DhatuInfo.create("dA", 3, Pada.UBHAYAPADA, ["to give"]),
    "pA": DhatuInfo.create("pA", 1, Pada.PARASMAIPADA, ["to drink", "to protect"]),
}
