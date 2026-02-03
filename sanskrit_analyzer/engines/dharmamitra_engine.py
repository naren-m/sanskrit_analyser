"""Dharmamitra ByT5 engine wrapper for neural Sanskrit analysis."""

from sanskrit_analyzer.engines.base import EngineBase, EngineResult, Segment
from sanskrit_analyzer.models.scripts import Script
from sanskrit_analyzer.utils.normalize import detect_script
from sanskrit_analyzer.utils.transliterate import transliterate


class DharmamitraEngine(EngineBase):
    """Dharmamitra ByT5-based analysis engine using neural models.

    Dharmamitra provides state-of-the-art neural morphological analysis
    using the ByT5-Sanskrit model for:
    - Sandhi resolution (compound word segmentation)
    - Lemmatization (finding root forms)
    - Morphosyntactic analysis (case, gender, number, etc.)
    """

    # Processing modes
    MODE_LEMMA = "lemma"
    MODE_UNSANDHIED = "unsandhied"
    MODE_FULL = "unsandhied-lemma-morphosyntax"

    def __init__(
        self,
        mode: str = "unsandhied-lemma-morphosyntax",
        device: str = "auto",
    ) -> None:
        """Initialize the Dharmamitra engine.

        Args:
            mode: Processing mode (lemma, unsandhied, or unsandhied-lemma-morphosyntax).
            device: Device to use (auto, cpu, cuda).
        """
        self._mode = mode
        self._device = device
        self._processor: object | None = None
        self._available = False
        self._init_error: str | None = None

        self._initialize()

    def _initialize(self) -> None:
        """Initialize the Dharmamitra processor."""
        try:
            from dharmamitra_sanskrit_grammar import DharmamitraSanskritProcessor

            self._processor = DharmamitraSanskritProcessor()
            self._available = True
        except ImportError as e:
            self._init_error = (
                f"Dharmamitra not installed: {e}. "
                "Install with: pip install dharmamitra-sanskrit-grammar"
            )
        except Exception as e:
            self._init_error = f"Failed to initialize Dharmamitra: {e}"

    @property
    def name(self) -> str:
        """Return the engine name."""
        return "dharmamitra"

    @property
    def weight(self) -> float:
        """Return the default weight for ensemble voting."""
        return 0.40

    @property
    def is_available(self) -> bool:
        """Check if the engine is available."""
        return self._available

    @property
    def mode(self) -> str:
        """Get the current processing mode."""
        return self._mode

    @mode.setter
    def mode(self, value: str) -> None:
        """Set the processing mode."""
        valid_modes = [self.MODE_LEMMA, self.MODE_UNSANDHIED, self.MODE_FULL]
        if value not in valid_modes:
            raise ValueError(f"Invalid mode: {value}. Must be one of {valid_modes}")
        self._mode = value

    def _normalize_to_iast(self, text: str) -> str:
        """Normalize input text to IAST for Dharmamitra.

        Dharmamitra works best with IAST input.
        """
        script = detect_script(text)
        if script == Script.IAST:
            return text
        return transliterate(text, script, Script.IAST)

    def _parse_tag(self, tag_str: str) -> dict:
        """Parse a Dharmamitra morphological tag string.

        Args:
            tag_str: Tag string like "Tense=Present, Mood=Indicative, Person=3"

        Returns:
            Dictionary of tag components.
        """
        result: dict = {"raw": tag_str}

        if not tag_str:
            return result

        # Parse comma-separated key=value pairs
        for part in tag_str.split(","):
            part = part.strip()
            if "=" in part:
                key, value = part.split("=", 1)
                result[key.strip().lower()] = value.strip()

        return result

    def _determine_pos(self, tag: dict) -> str | None:
        """Determine part of speech from tag dictionary."""
        if "tense" in tag or "mood" in tag or "person" in tag:
            return "verb"
        if "case" in tag or "gender" in tag:
            return "noun"
        if "degree" in tag:
            return "adjective"
        return None

    async def analyze(self, text: str) -> EngineResult:
        """Analyze Sanskrit text using Dharmamitra.

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
                error=self._init_error or "Dharmamitra not available",
            )

        if not text.strip():
            return EngineResult(
                engine=self.name,
                segments=[],
                confidence=0.0,
            )

        try:
            # Normalize to IAST
            iast_text = self._normalize_to_iast(text)

            # Call Dharmamitra API
            results = self._processor.process_batch(  # type: ignore
                [iast_text],
                mode=self._mode,
                human_readable_tags=True,
            )

            if not results or len(results) == 0:
                return EngineResult(
                    engine=self.name,
                    segments=[],
                    confidence=0.0,
                    error="No results from Dharmamitra",
                )

            # Convert to segments
            segments: list[Segment] = []
            result_data = results[0]

            for word_data in result_data.get("grammatical_analysis", []):
                # Parse morphological tag
                tag = self._parse_tag(word_data.get("tag", ""))

                # Build morphology string
                morph_parts = []
                pos = self._determine_pos(tag)
                if pos:
                    morph_parts.append(pos)
                if "tense" in tag:
                    morph_parts.append(tag["tense"].lower()[:4])
                if "mood" in tag:
                    morph_parts.append(tag["mood"].lower()[:3])
                if "person" in tag:
                    morph_parts.append(f"p{tag['person']}")
                if "number" in tag:
                    morph_parts.append(tag["number"].lower()[:2])
                if "case" in tag:
                    morph_parts.append(tag["case"].lower()[:3])
                if "gender" in tag:
                    morph_parts.append(tag["gender"].lower()[:3])

                morph_str = ".".join(morph_parts) if morph_parts else tag.get("raw")

                segment = Segment(
                    surface=word_data.get("unsandhied", ""),
                    lemma=word_data.get("lemma", ""),
                    morphology=morph_str,
                    confidence=0.92,  # Dharmamitra is neural, high but not rule-based
                    pos=pos,
                    meanings=word_data.get("meanings", []),
                )

                segments.append(segment)

            return EngineResult(
                engine=self.name,
                segments=segments,
                confidence=0.92 if segments else 0.0,
                raw_output=str(results),
            )

        except Exception as e:
            return EngineResult(
                engine=self.name,
                segments=[],
                confidence=0.0,
                error=f"Analysis failed: {e}",
            )
