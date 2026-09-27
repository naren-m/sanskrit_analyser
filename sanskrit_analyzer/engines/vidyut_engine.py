"""Vidyut engine wrapper for Paninian grammar-based analysis."""

import asyncio
import os

from sanskrit_analyzer.engines.base import EngineBase, EngineResult, Segment
from sanskrit_analyzer.models.scripts import Script
from sanskrit_analyzer.utils.normalize import detect_script
from sanskrit_analyzer.utils.transliterate import transliterate
from sanskrit_analyzer.vidyut_data import resolve_data_dir

# Where to download the bundle when no data directory is found.
DEFAULT_VIDYUT_DATA_PATH = os.path.expanduser("~/.vidyut-data")

# Vidyut enum member names -> models.morphology enum values.
_LINGA = {"Pum": "masculine", "Stri": "feminine", "Napumsaka": "neuter"}
_VIBHAKTI = {
    "Prathama": "nominative",
    "Dvitiya": "accusative",
    "Trtiya": "instrumental",
    "Caturthi": "dative",
    "Panchami": "ablative",
    "Sasthi": "genitive",
    "Saptami": "locative",
    "Sambodhana": "vocative",
}
_VACANA = {"Eka": "singular", "Dvi": "dual", "Bahu": "plural"}
_PURUSHA = {"Prathama": "third", "Madhyama": "second", "Uttama": "first"}
_LAKARA = {
    "Lat": "present",
    "Lan": "imperfect",
    "Lot": "imperative",
    "VidhiLin": "potential",
    "AshirLin": "benedictive",
    "Lit": "perfect",
    "Lun": "aorist",
    "Lrt": "future",
    "Lut": "periphrastic_future",
    "Lrn": "conditional",
}
_PRAYOGA = {"Kartari": "active", "Karmani": "passive", "Bhave": "passive"}


def _put(result: dict, key: str, table: dict[str, str], value: object) -> None:
    """Set result[key] from a vidyut enum member, skipping None and unknowns (e.g. Let)."""
    term = table.get(getattr(value, "name", ""))
    if term:
        result[key] = term


class VidyutEngine(EngineBase):
    """Vidyut-based analysis engine using Paninian grammar rules.

    Vidyut provides high-performance Sanskrit analysis based on the
    Ashtadhyayi, including sandhi splitting, morphological analysis,
    and prakriya (derivation) generation.
    """

    def __init__(self, data_path: str | None = None) -> None:
        """Initialize the Vidyut engine.

        Args:
            data_path: Path to vidyut data directory. Defaults to the bundle
                found by :func:`sanskrit_analyzer.vidyut_data.resolve_data_dir`
                (``VIDYUT_DATA_DIR``, ``<cwd>/vidyut-0.4.0``, ``~/.vidyut-data``),
                downloading to ``~/.vidyut-data`` when none exists.
        """
        if data_path is None:
            found = resolve_data_dir()
            data_path = str(found) if found else DEFAULT_VIDYUT_DATA_PATH
        self._data_path = data_path
        self._chedaka: object | None = None
        self._available = False
        self._init_error: str | None = None

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
    def is_available(self) -> bool:
        """Check if the engine is available."""
        return self._available

    def _normalize_to_slp1(self, text: str) -> str:
        """Normalize input text to SLP1 for Vidyut."""
        # The runner feeds engines already-normalized SLP1; plain ASCII
        # with no script markers (e.g. title-case "Bavati") must therefore
        # be treated as SLP1, not re-transliterated as IAST.
        script = detect_script(text, plain_ascii_default=Script.SLP1)
        if script == Script.SLP1:
            return text
        return transliterate(text, script, Script.SLP1)

    def _parse_pada_data(self, data: object) -> dict:
        """Read a Vidyut PadaEntry into English morphology terms.

        Values are the ``models.morphology`` enum values, so the tree builder
        can map them without guessing at abbreviations.
        """
        result: dict = {}
        name = type(data).__name__
        if name.endswith("Subanta"):
            result["type"] = "indeclinable" if data.is_avyaya else "noun"  # type: ignore[attr-defined]
            _put(result, "gender", _LINGA, data.linga)  # type: ignore[attr-defined]
            _put(result, "case", _VIBHAKTI, data.vibhakti)  # type: ignore[attr-defined]
            _put(result, "number", _VACANA, data.vacana)  # type: ignore[attr-defined]
        elif name.endswith("Tinanta"):
            result["type"] = "verb"
            _put(result, "person", _PURUSHA, data.purusha)  # type: ignore[attr-defined]
            _put(result, "number", _VACANA, data.vacana)  # type: ignore[attr-defined]
            _put(result, "tense", _LAKARA, data.lakara)  # type: ignore[attr-defined]
            _put(result, "voice", _PRAYOGA, data.prayoga)  # type: ignore[attr-defined]
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
            # Chedaka is sync Rust; keep it off the event loop.
            tokens = await asyncio.to_thread(self._chedaka.run, slp1_text)  # type: ignore

            for token in tokens:
                # Parse morphological data
                morph_data = self._parse_pada_data(token.data)

                morph_str = ".".join(morph_data.values()) or None

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
                raw_output=str([str(t.data) for t in tokens]),
            )

        except Exception as e:
            return EngineResult(
                engine=self.name,
                segments=[],
                confidence=0.0,
                error=f"Analysis failed: {e}",
            )
