"""Vidyut engine wrapper for Paninian grammar-based analysis."""

import os
from typing import Optional

from sanskrit_analyzer.engines.base import EngineBase, EngineResult, Segment
from sanskrit_analyzer.models.scripts import Script
from sanskrit_analyzer.utils.normalize import detect_script
from sanskrit_analyzer.utils.transliterate import transliterate

# Default data path for vidyut
DEFAULT_VIDYUT_DATA_PATH = os.path.expanduser("~/.vidyut-data")


class VidyutEngine(EngineBase):
    """Vidyut-based analysis engine using Paninian grammar rules.

    Vidyut provides high-performance Sanskrit analysis based on the
    Ashtadhyayi, including sandhi splitting, morphological analysis,
    and prakriya (derivation) generation.
    """

    def __init__(self, data_path: Optional[str] = None) -> None:
        """Initialize the Vidyut engine.

        Args:
            data_path: Path to vidyut data directory. Defaults to ~/.vidyut-data.
        """
        self._data_path = data_path or DEFAULT_VIDYUT_DATA_PATH
        self._chedaka: Optional[object] = None
        self._available = False
        self._init_error: Optional[str] = None

        self._initialize()

    def _initialize(self) -> None:
        """Initialize the Chedaka segmenter."""
        try:
            from vidyut.cheda import Chedaka

            if not os.path.exists(self._data_path):
                # Try to download data
                import vidyut

                os.makedirs(self._data_path, exist_ok=True)
                vidyut.download_data(self._data_path)

            self._chedaka = Chedaka(self._data_path)
            self._available = True
        except ImportError as e:
            self._init_error = f"Vidyut not installed: {e}"
        except Exception as e:
            self._init_error = f"Failed to initialize Vidyut: {e}"

    @property
    def name(self) -> str:
        """Return the engine name."""
        return "vidyut"

    @property
    def weight(self) -> float:
        """Return the default weight for ensemble voting."""
        return 0.35

    @property
    def is_available(self) -> bool:
        """Check if the engine is available."""
        return self._available

    def _normalize_to_slp1(self, text: str) -> str:
        """Normalize input text to SLP1 for Vidyut."""
        script = detect_script(text)
        if script == Script.SLP1:
            return text
        return transliterate(text, script, Script.SLP1)

    def _parse_pada_data(self, data: object) -> dict:
        """Parse Vidyut Pada data into a dictionary.

        Args:
            data: Vidyut PadaEntry object.

        Returns:
            Dictionary with morphological information.
        """
        result: dict = {"raw": str(data)}

        data_str = str(data)

        # Extract key information from the string representation
        if "Subanta" in data_str:
            result["type"] = "subanta"  # Nominal form
            if "Linga.Pum" in data_str:
                result["gender"] = "masculine"
            elif "Linga.Stri" in data_str:
                result["gender"] = "feminine"
            elif "Linga.Napumsaka" in data_str:
                result["gender"] = "neuter"

            # Extract vibhakti (case)
            for i, case in enumerate(
                [
                    "Prathama",
                    "Dvitiya",
                    "Trtiya",
                    "Caturthi",
                    "Pancami",
                    "Sasthi",
                    "Saptami",
                    "Sambodhana",
                ]
            ):
                if f"Vibhakti.{case}" in data_str:
                    result["case"] = case.lower()
                    result["case_number"] = i + 1
                    break

            # Extract vacana (number)
            if "Vacana.Eka" in data_str:
                result["number"] = "singular"
            elif "Vacana.Dvi" in data_str:
                result["number"] = "dual"
            elif "Vacana.Bahu" in data_str:
                result["number"] = "plural"

        elif "Tinanta" in data_str:
            result["type"] = "tinanta"  # Verbal form

            # Extract lakara (tense/mood)
            lakaras = ["Lat", "Lit", "Lut", "Lrt", "Let", "Lot", "Lan", "Lin", "Lun", "Lrn"]
            for lakara in lakaras:
                if f"Lakara.{lakara}" in data_str:
                    result["lakara"] = lakara.lower()
                    break

            # Extract purusha (person)
            if "Purusha.Prathama" in data_str:
                result["person"] = "third"
            elif "Purusha.Madhyama" in data_str:
                result["person"] = "second"
            elif "Purusha.Uttama" in data_str:
                result["person"] = "first"

            # Extract vacana
            if "Vacana.Eka" in data_str:
                result["number"] = "singular"
            elif "Vacana.Dvi" in data_str:
                result["number"] = "dual"
            elif "Vacana.Bahu" in data_str:
                result["number"] = "plural"

        # Extract gana if present
        ganas = [
            "Bhvadi",
            "Adadi",
            "Juhotyadi",
            "Divadi",
            "Svadi",
            "Tudadi",
            "Rudhadi",
            "Tanadi",
            "Kryadi",
            "Curadi",
        ]
        for i, gana in enumerate(ganas):
            if f"Gana.{gana}" in data_str:
                result["gana"] = i + 1
                result["gana_name"] = gana.lower()
                break

        return result

    async def analyze(self, text: str) -> EngineResult:
        """Analyze Sanskrit text using Vidyut.

        Args:
            text: Sanskrit text in any script.

        Returns:
            EngineResult with analyzed segments.
        """
        if not self._available:
            return EngineResult(
                engine=self.name,
                segments=[],
                confidence=0.0,
                error=self._init_error or "Vidyut not available",
            )

        try:
            # Normalize to SLP1
            slp1_text = self._normalize_to_slp1(text)

            # Run segmentation
            segments: list[Segment] = []
            tokens = self._chedaka.run(slp1_text)  # type: ignore

            for token in tokens:
                # Parse morphological data
                morph_data = self._parse_pada_data(token.data)

                # Build morphology string
                morph_parts = []
                if "type" in morph_data:
                    morph_parts.append(morph_data["type"])
                if "gender" in morph_data:
                    morph_parts.append(morph_data["gender"][:3])
                if "case" in morph_data:
                    morph_parts.append(morph_data["case"][:3])
                if "number" in morph_data:
                    morph_parts.append(morph_data["number"][:2])
                if "person" in morph_data:
                    morph_parts.append(morph_data["person"][:3])
                if "lakara" in morph_data:
                    morph_parts.append(morph_data["lakara"])

                morph_str = ".".join(morph_parts) if morph_parts else None

                segment = Segment(
                    surface=token.text,
                    lemma=token.lemma,
                    morphology=morph_str,
                    confidence=0.9,  # Vidyut is rule-based, high confidence
                    pos=morph_data.get("type"),
                )

                segments.append(segment)

            return EngineResult(
                engine=self.name,
                segments=segments,
                confidence=0.9 if segments else 0.0,
                raw_output=str([str(t.data) for t in self._chedaka.run(slp1_text)]),  # type: ignore
            )

        except Exception as e:
            return EngineResult(
                engine=self.name,
                segments=[],
                confidence=0.0,
                error=f"Analysis failed: {e}",
            )
