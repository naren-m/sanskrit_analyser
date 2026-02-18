"""Format converters for training data."""

from typing import Any


# Expected schema for grammar training output
GRAMMAR_OUTPUT_SCHEMA = {
    "type": "object",
    "required": ["sandhi_groups"],
    "properties": {
        "sandhi_groups": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["surface_form", "base_words"],
                "properties": {
                    "surface_form": {"type": "string"},
                    "base_words": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "required": ["lemma", "morphology"],
                        },
                    },
                },
            },
        },
        "confidence": {"type": "number"},
    },
}


class GrammarFormatConverter:
    """Convert analyzer output to grammar model training format.

    The grammar training format is:
    - input: "Parse: {sanskrit_text}"
    - output: structured JSON with sandhi_groups, words, morphology

    Example output:
    {
        "sandhi_groups": [
            {
                "surface_form": "रामो",
                "base_words": [{"lemma": "राम", "morphology": "noun-nom-sg-m"}]
            }
        ],
        "confidence": 0.95
    }
    """

    def convert(self, parse_result: dict[str, Any]) -> dict[str, Any]:
        """Convert analyzer ParseResult to training format.

        Args:
            parse_result: The analyzer's parse result dictionary.

        Returns:
            Formatted output for training.
        """
        sandhi_groups: list[dict[str, Any]] = []

        # Extract sandhi groups from parse result
        raw_groups = parse_result.get("sandhi_groups", [])
        for group in raw_groups:
            formatted_group: dict[str, Any] = {
                "surface_form": group.get("surface_form", ""),
                "base_words": [],
            }

            # Format base words
            for word in group.get("base_words", []):
                formatted_word = self._format_word(word)
                formatted_group["base_words"].append(formatted_word)

            sandhi_groups.append(formatted_group)

        # Build output
        output: dict[str, Any] = {
            "sandhi_groups": sandhi_groups,
        }

        # Add confidence if available
        if "confidence" in parse_result:
            conf = parse_result["confidence"]
            if hasattr(conf, "overall"):
                output["confidence"] = float(conf.overall)
            elif isinstance(conf, (int, float)):
                output["confidence"] = float(conf)

        return output

    def _format_word(self, word: dict[str, Any]) -> dict[str, Any]:
        """Format a single word entry.

        Args:
            word: Word dictionary from parse result.

        Returns:
            Formatted word for training output.
        """
        # Build morphology string
        morphology_parts = []
        if "pos" in word:
            morphology_parts.append(word["pos"])
        if "case" in word:
            morphology_parts.append(word["case"])
        if "number" in word:
            morphology_parts.append(word["number"])
        if "gender" in word:
            morphology_parts.append(word["gender"])
        if "person" in word:
            morphology_parts.append(word["person"])
        if "tense" in word:
            morphology_parts.append(word["tense"])
        if "voice" in word:
            morphology_parts.append(word["voice"])

        morphology = "-".join(morphology_parts) if morphology_parts else "unknown"

        formatted: dict[str, Any] = {
            "lemma": word.get("lemma", word.get("form", "")),
            "morphology": morphology,
        }

        # Add dhatu info for verbs
        if word.get("dhatu"):
            formatted["dhatu"] = f"√{word['dhatu']}"

        return formatted

    def to_training_example(
        self, text: str, parse_result: dict[str, Any]
    ) -> dict[str, Any]:
        """Create a complete training example.

        Args:
            text: The original Sanskrit text.
            parse_result: The analyzer's parse result.

        Returns:
            Complete training example with input and output.
        """
        return {
            "input": f"Parse: {text}",
            "output": self.convert(parse_result),
        }

    def validate_output(self, output: dict[str, Any]) -> list[str]:
        """Validate output against expected schema.

        Args:
            output: The formatted output to validate.

        Returns:
            List of validation errors (empty if valid).
        """
        errors: list[str] = []

        if "sandhi_groups" not in output:
            errors.append("Missing required field: sandhi_groups")
            return errors

        if not isinstance(output["sandhi_groups"], list):
            errors.append("sandhi_groups must be an array")
            return errors

        for i, group in enumerate(output["sandhi_groups"]):
            if "surface_form" not in group:
                errors.append(f"Group {i}: missing surface_form")
            if "base_words" not in group:
                errors.append(f"Group {i}: missing base_words")
            elif not isinstance(group["base_words"], list):
                errors.append(f"Group {i}: base_words must be an array")
            else:
                for j, word in enumerate(group["base_words"]):
                    if "lemma" not in word:
                        errors.append(f"Group {i}, word {j}: missing lemma")
                    if "morphology" not in word:
                        errors.append(f"Group {i}, word {j}: missing morphology")

        return errors


class DisambiguationFormatConverter:
    """Convert parse candidates to disambiguation training format."""

    # Placeholder - implementation in US-006
    pass
