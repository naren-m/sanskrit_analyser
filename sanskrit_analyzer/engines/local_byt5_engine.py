"""Local ByT5-Sanskrit engine for neural Sanskrit analysis.

This engine runs the ByT5-Sanskrit model locally using HuggingFace Transformers,
providing offline analysis without depending on external APIs.

The model supports three tasks via prefix:
- "S" - Sandhi segmentation (compound word splitting)
- "L" - Lemmatization (finding root forms)
- "M" - Morphosyntactic tagging (case, gender, number, etc.)

Reference: Nehrdich et al. (2024) "One Model is All You Need: ByT5-Sanskrit"
https://arxiv.org/abs/2409.13920
"""

import logging
from typing import Any

from sanskrit_analyzer.engines.base import EngineBase, EngineResult, Segment
from sanskrit_analyzer.models.scripts import Script
from sanskrit_analyzer.utils.normalize import detect_script
from sanskrit_analyzer.utils.transliterate import transliterate

logger = logging.getLogger(__name__)


class LocalByT5Engine(EngineBase):
    """Local ByT5-Sanskrit model engine.

    Runs the ByT5-Sanskrit model locally for:
    - Sandhi resolution (compound word segmentation)
    - Lemmatization (finding root forms)
    - Morphosyntactic analysis (case, gender, number, etc.)

    This provides the same capabilities as the Dharmamitra API but runs
    entirely offline with no rate limits or network dependencies.

    Example:
        engine = LocalByT5Engine()
        result = await engine.analyze("ramo vanam gacchati")
    """

    # Task prefixes for the model (from official repo)
    TASK_SEGMENT = "S"  # Sandhi segmentation
    TASK_LEMMA = "L"  # Lemmatization
    TASK_MORPHO = "SM"  # Segmentation + morphosyntax (no separate morph-only)
    TASK_COMBINED = "SLM"  # All three: segment + lemma + morphosyntax

    # Default model - the fine-tuned multitask model
    DEFAULT_MODEL = "chronbmm/sanskrit5-multitask"

    def __init__(
        self,
        model_name: str = DEFAULT_MODEL,
        device: str = "auto",
        max_length: int = 512,
        load_on_init: bool = True,
    ) -> None:
        """Initialize the local ByT5 engine.

        Args:
            model_name: HuggingFace model name or local path.
            device: Device to use ("auto", "cpu", "cuda", "mps").
            max_length: Maximum sequence length for generation.
            load_on_init: Whether to load model immediately or lazily.
        """
        self._model_name = model_name
        self._device_preference = device
        self._max_length = max_length

        self._model: Any = None
        self._tokenizer: Any = None
        self._device: str | None = None
        self._available = False
        self._init_error: str | None = None

        if load_on_init:
            self._load_model()

    def _get_device(self) -> str:
        """Determine the best device to use."""
        import torch

        if self._device_preference == "auto":
            if torch.cuda.is_available():
                return "cuda"
            elif hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
                return "mps"
            return "cpu"
        return self._device_preference

    def _load_model(self) -> None:
        """Load the ByT5 model and tokenizer."""
        try:
            from transformers import T5ForConditionalGeneration, AutoTokenizer
            import torch

            self._device = self._get_device()
            logger.info(
                "Loading ByT5-Sanskrit model '%s' on %s...",
                self._model_name,
                self._device,
            )

            # Load tokenizer
            self._tokenizer = AutoTokenizer.from_pretrained(self._model_name)

            # Load model
            self._model = T5ForConditionalGeneration.from_pretrained(
                self._model_name,
                torch_dtype=torch.float16 if self._device != "cpu" else torch.float32,
            )
            self._model.to(self._device)
            self._model.eval()

            self._available = True
            logger.info("ByT5-Sanskrit model loaded successfully")

        except ImportError as e:
            self._init_error = (
                f"Required packages not installed: {e}. "
                "Install with: pip install transformers torch"
            )
            logger.warning(self._init_error)
        except Exception as e:
            self._init_error = f"Failed to load ByT5-Sanskrit model: {e}"
            logger.error(self._init_error)

    def _ensure_loaded(self) -> bool:
        """Ensure model is loaded (lazy loading support)."""
        if not self._available and self._init_error is None:
            self._load_model()
        return self._available

    @property
    def name(self) -> str:
        """Return the engine name."""
        return "local_byt5"

    @property
    def weight(self) -> float:
        """Return the default weight for ensemble voting."""
        return 0.45  # Higher weight as this is the full local model

    @property
    def is_available(self) -> bool:
        """Check if the engine is available."""
        return self._available

    def _normalize_to_iast(self, text: str) -> str:
        """Normalize input text to IAST for the model.

        ByT5-Sanskrit works best with IAST/romanized input.
        """
        # The ensemble feeds engines already-normalized SLP1; plain ASCII
        # with no script markers (e.g. title-case "Bavati") must therefore
        # be treated as SLP1, not passed through as IAST.
        script = detect_script(text, plain_ascii_default=Script.SLP1)
        if script == Script.IAST:
            return text
        return transliterate(text, script, Script.IAST)

    def _generate(self, text: str, task_prefix: str) -> str:
        """Generate output for a given task.

        Args:
            text: Input text in IAST.
            task_prefix: Task prefix ("S", "L", or "M").

        Returns:
            Generated output string.
        """
        import torch

        # Prepare input with task prefix
        input_text = f"{task_prefix} {text}"

        # Tokenize
        inputs = self._tokenizer(
            input_text,
            return_tensors="pt",
            max_length=self._max_length,
            truncation=True,
        )
        inputs = {k: v.to(self._device) for k, v in inputs.items()}

        # Generate
        with torch.no_grad():
            outputs = self._model.generate(
                **inputs,
                max_length=self._max_length,
                num_beams=4,
                early_stopping=True,
            )

        # Decode
        result = self._tokenizer.decode(outputs[0], skip_special_tokens=True)
        return result.strip()

    def _strip_task_prefix(self, output: str) -> str:
        """Strip task prefix from model output if present.

        The model sometimes echoes the task prefix (S, L, M) in the output.

        Args:
            output: Raw model output.

        Returns:
            Output with task prefix stripped.
        """
        stripped = output.strip()
        # Check for single-letter prefix followed by space
        if len(stripped) >= 2 and stripped[0] in ("S", "L", "M") and stripped[1] == " ":
            return stripped[2:].strip()
        return stripped

    def _parse_segmentation(self, output: str) -> list[str]:
        """Parse segmentation output into word list.

        Args:
            output: Model output for segmentation task.

        Returns:
            List of segmented words.
        """
        # Strip task prefix if present
        clean_output = self._strip_task_prefix(output)
        # Model outputs underscore-separated words: rāmaḥ_vana_gacchati_
        words = clean_output.split("_")
        return [w.strip() for w in words if w.strip()]

    def _parse_lemmatization(self, output: str) -> list[str]:
        """Parse lemmatization output.

        Args:
            output: Model output for lemmatization task.

        Returns:
            List of lemmas (one per segmented word).
        """
        # Strip task prefix if present
        clean_output = self._strip_task_prefix(output)
        # Model outputs underscore-separated lemmas: rāma_vana_gam_
        lemmas = clean_output.split("_")
        return [l.strip() for l in lemmas if l.strip()]

    def _parse_combined(self, output: str) -> list[dict[str, str]]:
        """Parse combined SLM output (surface_lemma_tags).

        Args:
            output: Model output for SLM task.

        Returns:
            List of dicts with surface, lemma, and tags.
        """
        # Strip task prefix if present
        clean_output = self._strip_task_prefix(output)
        results = []

        # Format: "surface_lemma_TAGS surface_lemma_TAGS ..."
        # Example: "rāma_rāma_SNM vanam_vana_SANe gacchati_gam_VP3S"
        for token in clean_output.split():
            parts = token.split("_")
            if len(parts) >= 2:
                surface = parts[0]
                lemma = parts[1]
                tags = parts[2] if len(parts) > 2 else ""
                results.append({
                    "surface": surface,
                    "lemma": lemma,
                    "tags": tags,
                })
            elif parts:
                # Single part - use as surface and lemma
                results.append({
                    "surface": parts[0],
                    "lemma": parts[0],
                    "tags": "",
                })

        return results

    def _decode_tags(self, tags: str) -> tuple[str | None, str | None]:
        """Decode morphological tags into POS and morphology string.

        The model uses compact tags like:
        - SNM = Noun, Singular, Nominative, Masculine
        - SANe = Noun, Singular, Accusative, Neuter
        - VP3S = Verb, Present, 3rd person, Singular

        Args:
            tags: Compact tag string from model.

        Returns:
            Tuple of (pos, morph_string).
        """
        if not tags:
            return None, None

        # Determine POS from first letter
        pos = None
        if tags.startswith("V"):
            pos = "verb"
        elif tags.startswith("S") or tags.startswith("N"):
            pos = "noun"
        elif tags.startswith("A"):
            pos = "adjective"
        elif tags.startswith("I"):
            pos = "indeclinable"

        # Return the raw tag as morphology for now
        return pos, tags if tags else None

    async def analyze(self, text: str) -> EngineResult:
        """Analyze Sanskrit text using the local ByT5 model.

        Uses the combined SLM task for efficiency (segmentation + lemma + morphology
        in a single model call).

        Args:
            text: Sanskrit text in any script.

        Returns:
            EngineResult with analyzed segments.
        """
        if not self._ensure_loaded():
            return EngineResult(
                engine=self.name,
                segments=[],
                confidence=0.0,
                error=self._init_error or "ByT5 model not available",
            )

        if not text.strip():
            return EngineResult(
                engine=self.name,
                segments=[],
                confidence=0.0,
            )

        try:
            # Normalize to IAST for consistent processing
            iast_text = self._normalize_to_iast(text)

            # Use combined SLM task for efficiency (one model call)
            combined_output = self._generate(iast_text, self.TASK_COMBINED)
            logger.debug("Combined SLM output: %s", combined_output)

            # Parse combined output
            parsed = self._parse_combined(combined_output)

            # Build segments
            segments: list[Segment] = []
            for item in parsed:
                pos, morph_str = self._decode_tags(item.get("tags", ""))
                segment = Segment(
                    surface=item["surface"],
                    lemma=item["lemma"],
                    morphology=morph_str,
                    confidence=0.90,
                    pos=pos,
                )
                segments.append(segment)

            confidence = 0.90 if segments else 0.0

            return EngineResult(
                engine=self.name,
                segments=segments,
                confidence=confidence,
                raw_output=combined_output,
            )

        except Exception as e:
            logger.exception("Analysis failed")
            return EngineResult(
                engine=self.name,
                segments=[],
                confidence=0.0,
                error=f"Analysis failed: {e}",
            )

    def unload(self) -> None:
        """Unload the model to free memory."""
        if self._model is not None:
            del self._model
            self._model = None
        if self._tokenizer is not None:
            del self._tokenizer
            self._tokenizer = None
        self._available = False

        # Force garbage collection
        import gc
        import torch

        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()

        logger.info("ByT5-Sanskrit model unloaded")
