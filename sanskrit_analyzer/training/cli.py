"""CLI for training data generation."""

import argparse
import asyncio
import logging
import sys
from pathlib import Path

from sanskrit_analyzer.training.config import TrainingConfig
from sanskrit_analyzer.training.corpus_loader import CorpusLoader
from sanskrit_analyzer.training.data_generator import BatchAnalyzer, DisambiguationGenerator


def setup_logging(level: str) -> None:
    """Configure logging for CLI."""
    logging.basicConfig(
        level=getattr(logging, level.upper()),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )


async def generate_grammar_data(
    corpus_path: Path,
    output_path: Path,
    min_confidence: float,
    max_examples: int,
) -> int:
    """Generate grammar training data from a corpus.

    Args:
        corpus_path: Path to the corpus file.
        output_path: Path for output JSONL file.
        min_confidence: Minimum confidence threshold.
        max_examples: Maximum examples to generate (0 = unlimited).

    Returns:
        Number of examples generated.
    """
    config = TrainingConfig(
        min_confidence=min_confidence,
        max_examples=max_examples,
    )

    corpus = CorpusLoader(corpus_path)
    analyzer = BatchAnalyzer(config)

    return await analyzer.generate_training_data(corpus, output_path)


async def generate_disambig_data(
    corpus_path: Path,
    output_path: Path,
    max_examples: int,
) -> int:
    """Generate disambiguation training data from a corpus.

    Args:
        corpus_path: Path to the corpus file.
        output_path: Path for output JSONL file.
        max_examples: Maximum examples to generate (0 = unlimited).

    Returns:
        Number of examples generated.
    """
    import json

    config = TrainingConfig(max_examples=max_examples)
    corpus = CorpusLoader(corpus_path)
    analyzer = BatchAnalyzer(config)
    disambig = DisambiguationGenerator(config)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    count = 0

    with open(output_path, "w", encoding="utf-8") as f:
        async for result in analyzer.process_corpus(corpus):
            if result.num_parses >= 2:
                example = await disambig.process_analysis_result(result)
                if example:
                    f.write(json.dumps(example, ensure_ascii=False) + "\n")
                    count += 1

            if max_examples > 0 and count >= max_examples:
                break

    return count


def cmd_generate_grammar(args: argparse.Namespace) -> int:
    """Handle generate-grammar command."""
    setup_logging(args.log_level)
    logger = logging.getLogger(__name__)

    corpus_path = Path(args.corpus)
    output_path = Path(args.output)

    if not corpus_path.exists():
        logger.error(f"Corpus file not found: {corpus_path}")
        return 1

    logger.info(f"Generating grammar training data from {corpus_path}")
    logger.info(f"Output: {output_path}")
    logger.info(f"Min confidence: {args.min_confidence}")

    count = asyncio.run(
        generate_grammar_data(
            corpus_path,
            output_path,
            args.min_confidence,
            args.max_examples,
        )
    )

    logger.info(f"Generated {count} grammar training examples")
    print(f"\nSummary:")
    print(f"  Examples generated: {count}")
    print(f"  Output file: {output_path}")

    return 0


def cmd_generate_disambig(args: argparse.Namespace) -> int:
    """Handle generate-disambig command."""
    setup_logging(args.log_level)
    logger = logging.getLogger(__name__)

    corpus_path = Path(args.corpus)
    output_path = Path(args.output)

    if not corpus_path.exists():
        logger.error(f"Corpus file not found: {corpus_path}")
        return 1

    logger.info(f"Generating disambiguation training data from {corpus_path}")
    logger.info(f"Output: {output_path}")

    count = asyncio.run(
        generate_disambig_data(
            corpus_path,
            output_path,
            args.max_examples,
        )
    )

    logger.info(f"Generated {count} disambiguation training examples")
    print(f"\nSummary:")
    print(f"  Examples generated: {count}")
    print(f"  Output file: {output_path}")

    return 0


def cmd_validate(args: argparse.Namespace) -> int:
    """Handle validate command."""
    import json

    from sanskrit_analyzer.training.format_converter import GrammarFormatConverter

    setup_logging(args.log_level)
    logger = logging.getLogger(__name__)

    input_path = Path(args.input)
    if not input_path.exists():
        logger.error(f"Input file not found: {input_path}")
        return 1

    converter = GrammarFormatConverter()
    valid_count = 0
    invalid_count = 0
    errors: list[str] = []

    with open(input_path, encoding="utf-8") as f:
        for i, line in enumerate(f, 1):
            try:
                example = json.loads(line)
                output = example.get("output", {})
                validation_errors = converter.validate_output(output)

                if validation_errors:
                    invalid_count += 1
                    for err in validation_errors:
                        errors.append(f"Line {i}: {err}")
                else:
                    valid_count += 1

            except json.JSONDecodeError as e:
                invalid_count += 1
                errors.append(f"Line {i}: Invalid JSON - {e}")

    print(f"\nValidation Summary:")
    print(f"  Valid examples: {valid_count}")
    print(f"  Invalid examples: {invalid_count}")

    if errors and args.verbose:
        print(f"\nErrors:")
        for err in errors[:20]:  # Show first 20 errors
            print(f"  {err}")
        if len(errors) > 20:
            print(f"  ... and {len(errors) - 20} more errors")

    return 0 if invalid_count == 0 else 1


def cmd_stats(args: argparse.Namespace) -> int:
    """Handle stats command."""
    import json
    from collections import Counter

    setup_logging(args.log_level)

    input_path = Path(args.input)
    if not input_path.exists():
        print(f"Error: Input file not found: {input_path}")
        return 1

    total = 0
    confidence_sum = 0.0
    morphology_counter: Counter[str] = Counter()

    with open(input_path, encoding="utf-8") as f:
        for line in f:
            try:
                example = json.loads(line)
                total += 1

                # Extract confidence
                metadata = example.get("metadata", {})
                conf = metadata.get("confidence", 0.0)
                confidence_sum += conf

                # Count morphology types
                output = example.get("output", {})
                for group in output.get("sandhi_groups", []):
                    for word in group.get("base_words", []):
                        morph = word.get("morphology", "unknown")
                        pos = morph.split("-")[0] if "-" in morph else morph
                        morphology_counter[pos] += 1

            except json.JSONDecodeError:
                continue

    avg_confidence = confidence_sum / total if total > 0 else 0.0

    stats = {
        "total_examples": total,
        "average_confidence": round(avg_confidence, 3),
        "morphology_distribution": dict(morphology_counter.most_common(10)),
    }

    if args.json:
        print(json.dumps(stats, indent=2))
    else:
        print(f"\nTraining Data Statistics:")
        print(f"  Total examples: {total}")
        print(f"  Average confidence: {avg_confidence:.3f}")
        print(f"\n  Top morphology types:")
        for pos, count in morphology_counter.most_common(10):
            print(f"    {pos}: {count}")

    return 0


def main() -> int:
    """Main entry point for training CLI."""
    parser = argparse.ArgumentParser(
        description="Sanskrit Analyzer Training Data Generator",
        prog="sanskrit-train",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging level",
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # generate-grammar command
    grammar_parser = subparsers.add_parser(
        "generate-grammar",
        help="Generate grammar training data from corpus",
    )
    grammar_parser.add_argument(
        "--corpus",
        required=True,
        help="Path to corpus file",
    )
    grammar_parser.add_argument(
        "--output",
        required=True,
        help="Path for output JSONL file",
    )
    grammar_parser.add_argument(
        "--min-confidence",
        type=float,
        default=0.85,
        help="Minimum confidence threshold (default: 0.85)",
    )
    grammar_parser.add_argument(
        "--max-examples",
        type=int,
        default=0,
        help="Maximum examples to generate (0 = unlimited)",
    )
    grammar_parser.set_defaults(func=cmd_generate_grammar)

    # generate-disambig command
    disambig_parser = subparsers.add_parser(
        "generate-disambig",
        help="Generate disambiguation training data from corpus",
    )
    disambig_parser.add_argument(
        "--corpus",
        required=True,
        help="Path to corpus file",
    )
    disambig_parser.add_argument(
        "--output",
        required=True,
        help="Path for output JSONL file",
    )
    disambig_parser.add_argument(
        "--max-examples",
        type=int,
        default=0,
        help="Maximum examples to generate (0 = unlimited)",
    )
    disambig_parser.set_defaults(func=cmd_generate_disambig)

    # validate command
    validate_parser = subparsers.add_parser(
        "validate",
        help="Validate training data format",
    )
    validate_parser.add_argument(
        "--input",
        required=True,
        help="Path to JSONL file to validate",
    )
    validate_parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Show detailed errors",
    )
    validate_parser.set_defaults(func=cmd_validate)

    # stats command
    stats_parser = subparsers.add_parser(
        "stats",
        help="Generate statistics about training data",
    )
    stats_parser.add_argument(
        "--input",
        required=True,
        help="Path to JSONL file",
    )
    stats_parser.add_argument(
        "--json",
        action="store_true",
        help="Output as JSON",
    )
    stats_parser.set_defaults(func=cmd_stats)

    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        return 0

    result: int = args.func(args)
    return result


if __name__ == "__main__":
    sys.exit(main())
