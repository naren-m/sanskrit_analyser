#!/usr/bin/env python3
"""
Batch analysis example for Sanskrit Analyzer.

This example demonstrates how to:
- Process multiple Sanskrit texts efficiently
- Use batch analysis for better performance
- Export results to JSON
- Calculate statistics across a corpus
"""

import asyncio
import json
import logging
import sys
from collections import Counter
from pathlib import Path

from sanskrit_analyzer import Analyzer
from sanskrit_analyzer.config import Config

logger = logging.getLogger(__name__)


# Sample verses from Bhagavad Gita (Chapter 1)
SAMPLE_VERSES = [
    "धृतराष्ट्र उवाच",
    "धर्मक्षेत्रे कुरुक्षेत्रे समवेता युयुत्सवः",
    "मामकाः पाण्डवाश्चैव किमकुर्वत सञ्जय",
    "सञ्जय उवाच",
    "दृष्ट्वा तु पाण्डवानीकं व्यूढं दुर्योधनस्तदा",
    "आचार्यमुपसङ्गम्य राजा वचनमब्रवीत्",
]


async def analyze_batch(analyzer: Analyzer, texts: list[str]) -> list[dict]:
    """Analyze a batch of texts and return results."""
    results = []

    for text in texts:
        try:
            result = await analyzer.analyze(text, mode="academic")
            results.append({
                "text": text,
                "sentence_id": result.sentence_id,
                "normalized": result.normalized_slp1,
                "confidence": result.confidence.overall,
                "parse_count": len(result.parse_forest),
                "scripts": {
                    "devanagari": result.scripts.devanagari,
                    "iast": result.scripts.iast,
                },
                "words": extract_words(result),
            })
        except Exception as e:
            results.append({
                "text": text,
                "error": str(e),
            })
            logger.warning("Error analyzing '%s': %s", text, e, exc_info=True)

    return results


def extract_words(result) -> list[dict]:
    """Extract word information from an analysis result."""
    words = []

    if result.parse_forest:
        best_parse = result.parse_forest[0]
        for sg in best_parse.sandhi_groups:
            for word in sg.base_words:
                word_info = {
                    "lemma": word.lemma,
                    "surface": word.surface_form,
                    "confidence": word.confidence,
                }

                if word.morphology:
                    morph = word.morphology
                    word_info["morphology"] = {
                        k: v for k, v in {
                            "pos": morph.pos,
                            "gender": morph.gender,
                            "number": morph.number,
                            "case": morph.case,
                            "person": morph.person,
                            "tense": morph.tense,
                        }.items() if v
                    }

                if word.dhatu:
                    word_info["dhatu"] = {
                        "root": word.dhatu.dhatu,
                        "meaning": word.dhatu.meaning,
                        "gana": word.dhatu.gana,
                    }

                words.append(word_info)

    return words


def calculate_statistics(results: list[dict]) -> dict:
    """Calculate corpus statistics from analysis results."""
    successful = [r for r in results if "error" not in r]

    # Collect all words
    all_words = []
    all_pos = []
    all_dhatus = []

    for result in successful:
        for word in result.get("words", []):
            all_words.append(word["lemma"])
            if "morphology" in word and "pos" in word["morphology"]:
                all_pos.append(word["morphology"]["pos"])
            if "dhatu" in word:
                all_dhatus.append(word["dhatu"]["root"])

    # Word frequency
    word_freq = Counter(all_words)
    pos_freq = Counter(all_pos)
    dhatu_freq = Counter(all_dhatus)

    return {
        "total_texts": len(results),
        "successful_analyses": len(successful),
        "failed_analyses": len(results) - len(successful),
        "total_words": len(all_words),
        "unique_words": len(word_freq),
        "average_confidence": (
            sum(r["confidence"] for r in successful) / len(successful) if successful else 0
        ),
        "top_words": word_freq.most_common(10),
        "pos_distribution": dict(pos_freq),
        "unique_dhatus": len(dhatu_freq),
        "top_dhatus": dhatu_freq.most_common(5),
    }


async def main():
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    sys.stdout.write("=" * 60 + "\n")
    sys.stdout.write("Sanskrit Analyzer - Batch Analysis Example\n")
    sys.stdout.write("=" * 60 + "\n")

    # Initialize analyzer
    logger.info("Initializing analyzer...")
    config = Config()
    analyzer = Analyzer(config)

    # Analyze batch
    logger.info(f"Analyzing {len(SAMPLE_VERSES)} verses...")
    results = await analyze_batch(analyzer, SAMPLE_VERSES)

    # Calculate statistics
    stats = calculate_statistics(results)

    # Display statistics
    sys.stdout.write("\n" + "=" * 60 + "\n")
    sys.stdout.write("CORPUS STATISTICS\n")
    sys.stdout.write("=" * 60 + "\n")
    sys.stdout.write(f"\nTotal texts analyzed: {stats['total_texts']}\n")
    sys.stdout.write(f"Successful analyses: {stats['successful_analyses']}\n")
    sys.stdout.write(f"Failed analyses: {stats['failed_analyses']}\n")
    sys.stdout.write(f"\nTotal words extracted: {stats['total_words']}\n")
    sys.stdout.write(f"Unique lemmas: {stats['unique_words']}\n")
    sys.stdout.write(f"Average confidence: {stats['average_confidence']:.2%}\n")

    sys.stdout.write("\nTop 10 words by frequency:\n")
    for word, count in stats["top_words"]:
        sys.stdout.write(f"  {word}: {count}\n")

    sys.stdout.write("\nPOS distribution:\n")
    for pos, count in stats["pos_distribution"].items():
        sys.stdout.write(f"  {pos}: {count}\n")

    sys.stdout.write(f"\nUnique dhatus (verbal roots): {stats['unique_dhatus']}\n")
    if stats["top_dhatus"]:
        sys.stdout.write("Top dhatus:\n")
        for dhatu, count in stats["top_dhatus"]:
            sys.stdout.write(f"  √{dhatu}: {count}\n")

    # Export to JSON
    output_dir = Path(__file__).parent / "output"
    output_dir.mkdir(exist_ok=True)

    output_file = output_dir / "batch_results.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump({
            "results": results,
            "statistics": {
                **stats,
                "top_words": stats["top_words"],
                "top_dhatus": stats["top_dhatus"],
            }
        }, f, ensure_ascii=False, indent=2)

    logger.info(f"Results exported to: {output_file}")


if __name__ == "__main__":
    asyncio.run(main())
