#!/usr/bin/env python3
"""
Basic usage example for Sanskrit Analyzer.

This example demonstrates the core functionality of the Sanskrit Analyzer library:
- Analyzing Sanskrit text
- Accessing parse results
- Working with morphological information
"""

import asyncio
import logging
import sys

from sanskrit_analyzer import Analyzer
from sanskrit_analyzer.config import Config

logger = logging.getLogger(__name__)


async def main():
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    # Initialize the analyzer with default configuration
    logger.info("Initializing Sanskrit Analyzer...")
    config = Config()
    analyzer = Analyzer(config)

    # Example Sanskrit sentences
    sentences = [
        "रामः गच्छति",           # "Rama goes"
        "अहं पठामि",              # "I read"
        "सः पुस्तकं पठति",        # "He reads a book"
    ]

    for sentence in sentences:
        sys.stdout.write(f"\n{'=' * 60}\n")
        sys.stdout.write(f"Input: {sentence}\n")
        sys.stdout.write(f"{'=' * 60}\n")

        # Analyze the text
        result = await analyzer.analyze(sentence, mode="educational")

        # Display basic information
        sys.stdout.write(f"\nSentence ID: {result.sentence_id}\n")
        sys.stdout.write(f"Normalized (SLP1): {result.normalized_slp1}\n")
        sys.stdout.write(f"Overall Confidence: {result.confidence.overall:.2%}\n")

        # Script variants
        sys.stdout.write("\nScript Variants:\n")
        sys.stdout.write(f"  Devanagari: {result.scripts.devanagari}\n")
        sys.stdout.write(f"  IAST: {result.scripts.iast}\n")
        sys.stdout.write(f"  SLP1: {result.scripts.slp1}\n")

        # Parse results
        sys.stdout.write(f"\nNumber of parse candidates: {len(result.parse_forest)}\n")

        # Show the best (first) parse
        if result.parse_forest:
            best_parse = result.parse_forest[0]
            sys.stdout.write(f"\nBest Parse (confidence: {best_parse.confidence:.2%}):\n")

            for sg in best_parse.sandhi_groups:
                sys.stdout.write(f"\n  Sandhi Group: {sg.surface_form}\n")

                for word in sg.base_words:
                    sys.stdout.write(f"    Word: {word.lemma}\n")
                    sys.stdout.write(f"      Surface: {word.surface_form}\n")
                    sys.stdout.write(f"      Confidence: {word.confidence:.2%}\n")

                    if word.morphology:
                        morph = word.morphology
                        morph_parts = []
                        if morph.pos:
                            morph_parts.append(f"POS: {morph.pos}")
                        if morph.gender:
                            morph_parts.append(f"Gender: {morph.gender}")
                        if morph.number:
                            morph_parts.append(f"Number: {morph.number}")
                        if morph.case:
                            morph_parts.append(f"Case: {morph.case}")
                        if morph.person:
                            morph_parts.append(f"Person: {morph.person}")
                        if morph.tense:
                            morph_parts.append(f"Tense: {morph.tense}")
                        if morph_parts:
                            sys.stdout.write(f"      Morphology: {', '.join(morph_parts)}\n")

                    if word.dhatu:
                        sys.stdout.write(f"      Dhatu: √{word.dhatu.dhatu}\n")
                        if word.dhatu.meaning:
                            sys.stdout.write(f"      Meaning: {word.dhatu.meaning}\n")

                    if word.meanings:
                        sys.stdout.write(f"      Meanings: {', '.join(word.meanings[:3])}\n")

    # Show health check
    sys.stdout.write(f"\n{'=' * 60}\n")
    sys.stdout.write("Analyzer Health Check:\n")
    health = await analyzer.health_check()
    sys.stdout.write(f"  Status: {health.get('status', 'unknown')}\n")
    sys.stdout.write(f"  Version: {health.get('version', 'unknown')}\n")
    sys.stdout.write(f"  Engines: {', '.join(health.get('engines', []))}\n")


if __name__ == "__main__":
    asyncio.run(main())
