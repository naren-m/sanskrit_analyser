#!/usr/bin/env python3
"""
Integration example with Ramayanam project.

This example shows how to:
- Use Sanskrit Analyzer as a library in another project
- Process verses from a text corpus
- Build a knowledge graph from analysis results
- Store results for later retrieval

This is a template for integrating with the Ramayanam knowledge graph project.
"""

import asyncio
from dataclasses import dataclass
from typing import Optional
from sanskrit_analyzer import Analyzer
from sanskrit_analyzer.config import Config


@dataclass
class VerseAnalysis:
    """Analyzed verse with metadata."""
    kanda: str
    sarga: int
    verse_number: int
    verse_text: str
    analysis_id: str
    words: list[dict]
    dhatus: list[dict]
    confidence: float


class RamayanamIntegration:
    """
    Integration layer for Ramayanam knowledge graph.

    This class demonstrates how to use Sanskrit Analyzer
    to build a knowledge graph from Ramayanam verses.
    """

    def __init__(self, config: Optional[Config] = None):
        self.config = config or Config()
        self.analyzer = Analyzer(self.config)
        self.analyzed_verses: list[VerseAnalysis] = []

    async def analyze_verse(
        self,
        verse_text: str,
        kanda: str,
        sarga: int,
        verse_number: int,
    ) -> VerseAnalysis:
        """
        Analyze a single verse and extract entities for knowledge graph.
        """
        # Analyze with academic mode for maximum detail
        result = await self.analyzer.analyze(verse_text, mode="academic")

        # Extract words and their properties
        words = []
        dhatus = []

        if result.parse_forest:
            best_parse = result.parse_forest[0]

            for sg in best_parse.sandhi_groups:
                for word in sg.base_words:
                    word_entry = {
                        "lemma": word.lemma,
                        "surface_form": word.surface_form,
                        "devanagari": word.scripts.devanagari if word.scripts else word.lemma,
                        "iast": word.scripts.iast if word.scripts else "",
                        "confidence": word.confidence,
                        "meanings": word.meanings,
                    }

                    # Add morphological information
                    if word.morphology:
                        morph = word.morphology
                        word_entry["morphology"] = {
                            "pos": morph.pos,
                            "gender": morph.gender,
                            "number": morph.number,
                            "case": morph.case,
                            "person": morph.person,
                            "tense": morph.tense,
                            "mood": morph.mood,
                            "voice": morph.voice,
                        }

                    words.append(word_entry)

                    # Track dhatus separately for verb analysis
                    if word.dhatu:
                        dhatus.append({
                            "root": word.dhatu.dhatu,
                            "meaning": word.dhatu.meaning,
                            "gana": word.dhatu.gana,
                            "pada": word.dhatu.pada,
                            "verse_location": f"{kanda}.{sarga}.{verse_number}",
                            "surface_form": word.surface_form,
                        })

        verse_analysis = VerseAnalysis(
            kanda=kanda,
            sarga=sarga,
            verse_number=verse_number,
            verse_text=verse_text,
            analysis_id=result.sentence_id,
            words=words,
            dhatus=dhatus,
            confidence=result.confidence.overall,
        )

        self.analyzed_verses.append(verse_analysis)
        return verse_analysis

    async def analyze_sarga(
        self,
        verses: list[str],
        kanda: str,
        sarga: int,
    ) -> list[VerseAnalysis]:
        """Analyze all verses in a sarga."""
        results = []

        for i, verse in enumerate(verses, 1):
            print(f"  Analyzing verse {i}/{len(verses)}...")
            analysis = await self.analyze_verse(verse, kanda, sarga, i)
            results.append(analysis)

        return results

    def extract_character_names(self) -> list[dict]:
        """
        Extract potential character names from analyzed verses.

        In Ramayanam, proper nouns are typically:
        - Nominative case nouns
        - Capitalized in IAST
        - Often with specific suffixes
        """
        characters = []

        for verse in self.analyzed_verses:
            for word in verse.words:
                morph = word.get("morphology", {})

                # Check for nominative case nouns
                if morph.get("case") == "nominative" and morph.get("pos") in ["noun", "proper_noun"]:
                    characters.append({
                        "name": word["lemma"],
                        "devanagari": word.get("devanagari", ""),
                        "location": f"{verse.kanda}.{verse.sarga}.{verse.verse_number}",
                    })

        return characters

    def get_dhatu_usage(self) -> dict[str, list[dict]]:
        """Get all verb usages grouped by dhatu root."""
        dhatu_usage: dict[str, list[dict]] = {}

        for verse in self.analyzed_verses:
            for dhatu in verse.dhatus:
                root = dhatu["root"]
                if root not in dhatu_usage:
                    dhatu_usage[root] = []
                dhatu_usage[root].append({
                    "location": dhatu["verse_location"],
                    "surface_form": dhatu["surface_form"],
                    "meaning": dhatu["meaning"],
                })

        return dhatu_usage

    def to_knowledge_graph_nodes(self) -> list[dict]:
        """
        Convert analyzed verses to knowledge graph nodes.

        This format is suitable for import into Neo4j or similar graph databases.
        """
        nodes = []

        for verse in self.analyzed_verses:
            # Verse node
            nodes.append({
                "type": "Verse",
                "id": verse.analysis_id,
                "properties": {
                    "kanda": verse.kanda,
                    "sarga": verse.sarga,
                    "verse_number": verse.verse_number,
                    "text": verse.verse_text,
                    "confidence": verse.confidence,
                },
            })

            # Word nodes with relationships to verse
            for word in verse.words:
                word_id = f"{verse.analysis_id}_{word['lemma']}"
                nodes.append({
                    "type": "Word",
                    "id": word_id,
                    "properties": {
                        "lemma": word["lemma"],
                        "devanagari": word.get("devanagari", ""),
                        "meanings": word.get("meanings", []),
                        **word.get("morphology", {}),
                    },
                    "relationships": [
                        {"type": "APPEARS_IN", "target": verse.analysis_id},
                    ],
                })

            # Dhatu nodes
            for dhatu in verse.dhatus:
                dhatu_id = f"dhatu_{dhatu['root']}"
                nodes.append({
                    "type": "Dhatu",
                    "id": dhatu_id,
                    "properties": {
                        "root": dhatu["root"],
                        "meaning": dhatu["meaning"],
                        "gana": dhatu["gana"],
                    },
                    "relationships": [
                        {"type": "USED_IN", "target": verse.analysis_id},
                    ],
                })

        return nodes


async def main():
    """Demo of Ramayanam integration."""
    print("=" * 60)
    print("Sanskrit Analyzer - Ramayanam Integration Example")
    print("=" * 60)

    # Sample verses from Balakanda
    sample_verses = [
        "तपः स्वाध्यायनिरतं तपस्वी वाग्विदां वरम्",
        "नारदं परिपप्रच्छ वाल्मीकिर्मुनिपुङ्गवम्",
        "को न्वस्मिन्साम्प्रतं लोके गुणवान्कश्च वीर्यवान्",
        "धर्मज्ञश्च कृतज्ञश्च सत्यवाक्यो दृढव्रतः",
    ]

    # Initialize integration
    integration = RamayanamIntegration()

    # Analyze verses
    print("\nAnalyzing Balakanda sample verses...")
    results = await integration.analyze_sarga(
        verses=sample_verses,
        kanda="Balakanda",
        sarga=1,
    )

    # Show results
    print("\n" + "=" * 60)
    print("ANALYSIS RESULTS")
    print("=" * 60)

    for verse in results:
        print(f"\nVerse {verse.kanda}.{verse.sarga}.{verse.verse_number}:")
        print(f"  Text: {verse.verse_text}")
        print(f"  Confidence: {verse.confidence:.2%}")
        print(f"  Words: {len(verse.words)}")
        print(f"  Dhatus: {len(verse.dhatus)}")

        if verse.dhatus:
            print("  Verbal roots:")
            for d in verse.dhatus:
                print(f"    √{d['root']}: {d['meaning']}")

    # Extract character names
    print("\n" + "=" * 60)
    print("POTENTIAL CHARACTER NAMES")
    print("=" * 60)
    characters = integration.extract_character_names()
    for char in characters[:10]:  # First 10
        print(f"  {char['name']} ({char['devanagari']}) - {char['location']}")

    # Show dhatu usage
    print("\n" + "=" * 60)
    print("DHATU USAGE")
    print("=" * 60)
    dhatu_usage = integration.get_dhatu_usage()
    for root, usages in list(dhatu_usage.items())[:5]:
        print(f"\n  √{root}:")
        for usage in usages:
            print(f"    {usage['surface_form']} at {usage['location']}")

    # Generate knowledge graph nodes
    print("\n" + "=" * 60)
    print("KNOWLEDGE GRAPH NODES")
    print("=" * 60)
    nodes = integration.to_knowledge_graph_nodes()
    node_types = {}
    for node in nodes:
        node_type = node["type"]
        node_types[node_type] = node_types.get(node_type, 0) + 1

    print("\nNode counts by type:")
    for node_type, count in node_types.items():
        print(f"  {node_type}: {count}")


if __name__ == "__main__":
    asyncio.run(main())
