#!/usr/bin/env python3
"""
Basic usage example for Sanskrit Analyzer.

This example demonstrates the core functionality of the Sanskrit Analyzer library:
- Analyzing Sanskrit text
- Accessing parse results
- Working with morphological information
"""

import asyncio
from sanskrit_analyzer import Analyzer
from sanskrit_analyzer.config import Config


async def main():
    # Initialize the analyzer with default configuration
    print("Initializing Sanskrit Analyzer...")
    config = Config()
    analyzer = Analyzer(config)

    # Example Sanskrit sentences
    sentences = [
        "रामः गच्छति",           # "Rama goes"
        "अहं पठामि",              # "I read"
        "सः पुस्तकं पठति",        # "He reads a book"
    ]

    for sentence in sentences:
        print(f"\n{'=' * 60}")
        print(f"Input: {sentence}")
        print(f"{'=' * 60}")

        # Analyze the text
        result = await analyzer.analyze(sentence, mode="educational")

        # Display basic information
        print(f"\nSentence ID: {result.sentence_id}")
        print(f"Normalized (SLP1): {result.normalized_slp1}")
        print(f"Overall Confidence: {result.confidence.overall:.2%}")

        # Script variants
        print(f"\nScript Variants:")
        print(f"  Devanagari: {result.scripts.devanagari}")
        print(f"  IAST: {result.scripts.iast}")
        print(f"  SLP1: {result.scripts.slp1}")

        # Parse results
        print(f"\nNumber of parse candidates: {len(result.parse_forest)}")

        # Show the best (first) parse
        if result.parse_forest:
            best_parse = result.parse_forest[0]
            print(f"\nBest Parse (confidence: {best_parse.confidence:.2%}):")

            for sg in best_parse.sandhi_groups:
                print(f"\n  Sandhi Group: {sg.surface_form}")

                for word in sg.base_words:
                    print(f"    Word: {word.lemma}")
                    print(f"      Surface: {word.surface_form}")
                    print(f"      Confidence: {word.confidence:.2%}")

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
                            print(f"      Morphology: {', '.join(morph_parts)}")

                    if word.dhatu:
                        print(f"      Dhatu: √{word.dhatu.dhatu}")
                        if word.dhatu.meaning:
                            print(f"      Meaning: {word.dhatu.meaning}")

                    if word.meanings:
                        print(f"      Meanings: {', '.join(word.meanings[:3])}")

    # Show health check
    print(f"\n{'=' * 60}")
    print("Analyzer Health Check:")
    health = await analyzer.health_check()
    print(f"  Status: {health.get('status', 'unknown')}")
    print(f"  Version: {health.get('version', 'unknown')}")
    print(f"  Engines: {', '.join(health.get('engines', []))}")


if __name__ == "__main__":
    asyncio.run(main())
