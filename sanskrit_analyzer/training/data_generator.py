"""Training data generation from Sanskrit corpora."""

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, AsyncIterator

from sanskrit_analyzer.analyzer import Analyzer
from sanskrit_analyzer.config import Config
from sanskrit_analyzer.training.config import TrainingConfig
from sanskrit_analyzer.training.corpus_loader import CorpusEntry, CorpusLoader

logger = logging.getLogger(__name__)


def _extract_confidence(confidence_value: Any) -> float:
    """Extract float confidence from various formats.

    Args:
        confidence_value: Confidence as float, int, or object with .overall attribute.

    Returns:
        Float confidence value.
    """
    if hasattr(confidence_value, "overall"):
        return float(confidence_value.overall)
    return float(confidence_value) if confidence_value else 0.0


@dataclass
class AnalysisResult:
    """Result of analyzing a corpus entry.

    Attributes:
        entry: The original corpus entry.
        parse_result: The analysis result dictionary.
        confidence: Confidence score of the analysis.
        num_parses: Number of parse candidates.
    """

    entry: CorpusEntry
    parse_result: dict[str, Any]
    confidence: float
    num_parses: int


class BatchAnalyzer:
    """Process corpus texts through the analyzer in batch mode.

    Example usage:
        config = TrainingConfig(min_confidence=0.85)
        analyzer = BatchAnalyzer(config)
        async for result in analyzer.process_corpus(corpus_loader):
            if result.confidence >= config.min_confidence:
                save_result(result)
    """

    def __init__(self, config: TrainingConfig | None = None) -> None:
        """Initialize the batch analyzer.

        Args:
            config: Training configuration. Uses defaults if not provided.
        """
        self.config = config or TrainingConfig()
        self._analyzer: Analyzer | None = None

    def _get_analyzer(self) -> Analyzer:
        """Get or create the analyzer instance."""
        if self._analyzer is None:
            self._analyzer = Analyzer(Config())
        return self._analyzer

    async def analyze_entry(self, entry: CorpusEntry) -> AnalysisResult | None:
        """Analyze a single corpus entry.

        Args:
            entry: The corpus entry to analyze.

        Returns:
            AnalysisResult if successful, None if analysis failed.
        """
        try:
            analyzer = self._get_analyzer()
            result = await analyzer.analyze(entry.text)

            raw_confidence = result.confidence if hasattr(result, "confidence") else 0.0
            confidence = _extract_confidence(raw_confidence)
            num_parses = len(result.parse_forest) if hasattr(result, "parse_forest") else 1
            parse_dict = result.model_dump() if hasattr(result, "model_dump") else {}

            return AnalysisResult(
                entry=entry,
                parse_result=parse_dict,
                confidence=confidence,
                num_parses=num_parses,
            )
        except Exception as e:
            logger.warning(f"Failed to analyze '{entry.text[:50]}...': {e}")
            return None

    async def process_corpus(
        self, corpus: CorpusLoader
    ) -> AsyncIterator[AnalysisResult]:
        """Process all entries in a corpus.

        Args:
            corpus: The corpus loader to process.

        Yields:
            AnalysisResult for each successfully analyzed entry.
        """
        processed = 0
        for entry in corpus:
            result = await self.analyze_entry(entry)
            if result is not None:
                processed += 1
                if processed % 100 == 0:
                    logger.info(f"Processed {processed} entries")
                yield result

            # Check max examples limit
            if self.config.max_examples > 0 and processed >= self.config.max_examples:
                logger.info(f"Reached max examples limit: {self.config.max_examples}")
                break

    async def generate_training_data(
        self,
        corpus: CorpusLoader,
        output_path: Path | None = None,
    ) -> int:
        """Generate training data from a corpus and save to JSONL.

        Args:
            corpus: The corpus loader to process.
            output_path: Output file path. Uses config default if not provided.

        Returns:
            Number of examples written.
        """
        output_path = output_path or self.config.grammar_output_path()
        output_path.parent.mkdir(parents=True, exist_ok=True)

        count = 0
        with open(output_path, "w", encoding="utf-8") as f:
            async for result in self.process_corpus(corpus):
                if result.confidence >= self.config.min_confidence:
                    example = {
                        "input": f"Parse: {result.entry.text}",
                        "output": result.parse_result,
                        "metadata": {
                            "corpus": result.entry.metadata.corpus,
                            "chapter": result.entry.metadata.chapter,
                            "verse": result.entry.metadata.verse,
                            "confidence": result.confidence,
                        },
                    }
                    f.write(json.dumps(example, ensure_ascii=False) + "\n")
                    count += 1

        logger.info(f"Generated {count} training examples to {output_path}")
        return count


class DisambiguationGenerator:
    """Generate disambiguation training examples from ambiguous parses.

    Generates training examples for the disambiguation model by:
    1. Finding sentences with multiple parse candidates
    2. Selecting the highest-confidence parse as "correct"
    3. Generating reasoning using templates

    Example output:
    {
        "input": {
            "text": "कृष्णं वन्दे",
            "parses": [...],
            "context": "Devotional verse"
        },
        "output": {
            "selected": 0,
            "reasoning": "Rule 'verb_agreement' matched...",
            "confidence": 0.87
        }
    }
    """

    def __init__(self, config: TrainingConfig | None = None) -> None:
        """Initialize the disambiguation generator.

        Args:
            config: Training configuration.
        """
        self.config = config or TrainingConfig()

    def generate_example(
        self,
        text: str,
        parses: list[dict[str, Any]],
        selected_index: int,
        context: str = "",
    ) -> dict[str, Any]:
        """Generate a single disambiguation training example.

        Args:
            text: The Sanskrit text.
            parses: List of parse candidates.
            selected_index: Index of the selected (correct) parse.
            context: Optional context string.

        Returns:
            Complete disambiguation training example.
        """
        from sanskrit_analyzer.training.reasoning_templates import (
            detect_applicable_rule,
            fill_template,
        )

        rule_name, params = detect_applicable_rule(parses, selected_index)
        reasoning = fill_template(rule_name, **params)
        selected_conf = _extract_confidence(parses[selected_index].get("confidence", 0.5))

        return {
            "input": {
                "text": text,
                "parses": [
                    {
                        "interpretation": p.get("interpretation", f"Parse {i}"),
                        "confidence": _extract_confidence(p.get("confidence", 0.5)),
                    }
                    for i, p in enumerate(parses)
                ],
                "context": context,
            },
            "output": {
                "selected": selected_index,
                "reasoning": reasoning,
                "confidence": selected_conf,
            },
        }

    async def process_analysis_result(
        self,
        result: AnalysisResult,
        context: str = "",
    ) -> dict[str, Any] | None:
        """Generate disambiguation example from an analysis result.

        Args:
            result: The analysis result with multiple parses.
            context: Optional context string.

        Returns:
            Disambiguation example if multiple parses, None otherwise.
        """
        if result.num_parses < 2:
            return None

        # Get parse forest from result
        parse_forest = result.parse_result.get("parse_forest", [])
        if len(parse_forest) < 2:
            return None

        # Select highest confidence parse
        best_index = 0
        best_conf = 0.0
        for i, parse in enumerate(parse_forest):
            conf = _extract_confidence(parse.get("confidence", 0.0))
            if conf > best_conf:
                best_conf = conf
                best_index = i

        return self.generate_example(
            text=result.entry.text,
            parses=parse_forest,
            selected_index=best_index,
            context=context or result.entry.metadata.corpus,
        )
