"""Grammar resource providers for MCP server (sandhi-rules, pratyayas, sutras)."""

import json
from pathlib import Path
from typing import Any

import yaml
from mcp.server import Server
from mcp.types import Resource


def _load_yaml(filename: str) -> dict[str, Any]:
    """Load YAML data file from the data directory."""
    data_dir = Path(__file__).parent.parent.parent / "data"
    filepath = data_dir / filename

    if not filepath.exists():
        return {}

    with open(filepath, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def register_grammar_resources(server: Server) -> None:
    """Register grammar resources with the MCP server.

    Args:
        server: MCP server instance.
    """

    @server.list_resources()
    async def list_resources() -> list[Resource]:
        return [
            # Sandhi Rules Resources
            Resource(
                uri="grammar://sandhi-rules",  # type: ignore[arg-type]
                name="Sandhi Rules Index",
                description="Overview of sandhi (euphonic combination) rules",
                mimeType="application/json",
            ),
            Resource(
                uri="grammar://sandhi-rules/vowel",  # type: ignore[arg-type]
                name="Vowel Sandhi Rules (ac-sandhi)",
                description="Rules for vowel sandhi (ac-sandhi)",
                mimeType="application/json",
            ),
            Resource(
                uri="grammar://sandhi-rules/consonant",  # type: ignore[arg-type]
                name="Consonant Sandhi Rules (hal-sandhi)",
                description="Rules for consonant sandhi (hal-sandhi)",
                mimeType="application/json",
            ),
            Resource(
                uri="grammar://sandhi-rules/visarga",  # type: ignore[arg-type]
                name="Visarga Sandhi Rules",
                description="Rules for visarga sandhi",
                mimeType="application/json",
            ),
            # Pratyaya Resources
            Resource(
                uri="grammar://pratyayas",  # type: ignore[arg-type]
                name="Pratyayas Index",
                description="Overview of pratyayas (suffixes)",
                mimeType="application/json",
            ),
            Resource(
                uri="grammar://pratyayas/krt",  # type: ignore[arg-type]
                name="Krt Pratyayas",
                description="Primary verbal suffixes (kṛt pratyayas)",
                mimeType="application/json",
            ),
            Resource(
                uri="grammar://pratyayas/taddhita",  # type: ignore[arg-type]
                name="Taddhita Pratyayas",
                description="Secondary nominal suffixes (taddhita pratyayas)",
                mimeType="application/json",
            ),
            Resource(
                uri="grammar://pratyayas/tin",  # type: ignore[arg-type]
                name="Tin Pratyayas",
                description="Verb endings (tiṅ pratyayas)",
                mimeType="application/json",
            ),
            Resource(
                uri="grammar://pratyayas/sup",  # type: ignore[arg-type]
                name="Sup Pratyayas",
                description="Noun endings (sup pratyayas)",
                mimeType="application/json",
            ),
            # Sutra Resources
            Resource(
                uri="grammar://sutras",  # type: ignore[arg-type]
                name="Ashtadhyayi Overview",
                description="Overview of Panini's Ashtadhyayi (8 chapters, 4 sections each)",
                mimeType="application/json",
            ),
            Resource(
                uri="grammar://sutras/1/1",  # type: ignore[arg-type]
                name="Adhyaya 1, Pada 1",
                description="Sutras from Ashtadhyayi 1.1",
                mimeType="application/json",
            ),
            Resource(
                uri="grammar://sutras/1/2",  # type: ignore[arg-type]
                name="Adhyaya 1, Pada 2",
                description="Sutras from Ashtadhyayi 1.2",
                mimeType="application/json",
            ),
            Resource(
                uri="grammar://sutras/1/3",  # type: ignore[arg-type]
                name="Adhyaya 1, Pada 3",
                description="Sutras from Ashtadhyayi 1.3",
                mimeType="application/json",
            ),
            Resource(
                uri="grammar://sutras/1/4",  # type: ignore[arg-type]
                name="Adhyaya 1, Pada 4",
                description="Sutras from Ashtadhyayi 1.4",
                mimeType="application/json",
            ),
        ]

    @server.read_resource()
    async def read_resource(uri: str) -> str:
        # Sandhi rules
        if uri == "grammar://sandhi-rules":
            return _get_sandhi_rules_index()
        elif uri == "grammar://sandhi-rules/vowel":
            return _get_sandhi_rules_category("vowel")
        elif uri == "grammar://sandhi-rules/consonant":
            return _get_sandhi_rules_category("consonant")
        elif uri == "grammar://sandhi-rules/visarga":
            return _get_sandhi_rules_category("visarga")

        # Pratyayas
        elif uri == "grammar://pratyayas":
            return _get_pratyayas_index()
        elif uri == "grammar://pratyayas/krt":
            return _get_pratyayas_category("krt")
        elif uri == "grammar://pratyayas/taddhita":
            return _get_pratyayas_category("taddhita")
        elif uri == "grammar://pratyayas/tin":
            return _get_pratyayas_category("tin")
        elif uri == "grammar://pratyayas/sup":
            return _get_pratyayas_category("sup")

        # Sutras
        elif uri == "grammar://sutras":
            return _get_sutras_overview()
        elif uri.startswith("grammar://sutras/"):
            parts = uri.replace("grammar://sutras/", "").split("/")
            if len(parts) == 2:
                try:
                    adhyaya = int(parts[0])
                    pada = int(parts[1])
                    return _get_sutras_section(adhyaya, pada)
                except ValueError:
                    return json.dumps({"error": f"Invalid sutra reference: {uri}"})
            elif "search" in parts[0]:
                query = uri.split("?q=")[1] if "?q=" in uri else ""
                return _search_sutras(query)

        return json.dumps({"error": f"Unknown resource: {uri}"})


def _get_sandhi_rules_index() -> str:
    """Get sandhi rules overview."""
    data = _load_yaml("sandhi_rules.yaml")

    if not data:
        return json.dumps({
            "description": "Sandhi rules data not yet loaded. Placeholder for sandhi rules.",
            "categories": ["vowel", "consonant", "visarga"],
            "note": "Full sandhi rules database to be populated.",
        }, indent=2, ensure_ascii=False)

    return json.dumps({
        "description": data.get("description", "Sandhi rules of Sanskrit"),
        "categories": list(data.get("categories", {}).keys()),
        "total_rules": sum(
            len(rules) for rules in data.get("categories", {}).values()
        ),
    }, indent=2, ensure_ascii=False)


def _get_sandhi_rules_category(category: str) -> str:
    """Get sandhi rules for a specific category."""
    data = _load_yaml("sandhi_rules.yaml")
    categories = data.get("categories", {})

    if category not in categories:
        return json.dumps({
            "category": category,
            "rules": [],
            "note": f"No rules found for category: {category}",
        }, indent=2, ensure_ascii=False)

    return json.dumps({
        "category": category,
        "rules": categories[category],
    }, indent=2, ensure_ascii=False)


def _get_pratyayas_index() -> str:
    """Get pratyayas overview."""
    data = _load_yaml("pratyayas.yaml")

    if not data:
        return json.dumps({
            "description": "Pratyayas (suffixes) data not yet loaded. Placeholder for pratyayas.",
            "categories": ["krt", "taddhita", "tin", "sup"],
            "note": "Full pratyayas database to be populated.",
        }, indent=2, ensure_ascii=False)

    return json.dumps({
        "description": data.get("description", "Sanskrit pratyayas (suffixes)"),
        "categories": list(data.get("categories", {}).keys()),
        "total_pratyayas": sum(
            len(items) for items in data.get("categories", {}).values()
        ),
    }, indent=2, ensure_ascii=False)


def _get_pratyayas_category(category: str) -> str:
    """Get pratyayas for a specific category."""
    data = _load_yaml("pratyayas.yaml")
    categories = data.get("categories", {})

    if category not in categories:
        return json.dumps({
            "category": category,
            "pratyayas": [],
            "note": f"No pratyayas found for category: {category}",
        }, indent=2, ensure_ascii=False)

    return json.dumps({
        "category": category,
        "pratyayas": categories[category],
    }, indent=2, ensure_ascii=False)


def _get_sutras_overview() -> str:
    """Get Ashtadhyayi overview."""
    data = _load_yaml("sutras.yaml")

    if not data:
        return json.dumps({
            "title": "Aṣṭādhyāyī (अष्टाध्यायी)",
            "author": "Pāṇini (पाणिनि)",
            "description": "The foundational text of Sanskrit grammar, consisting of 8 chapters (adhyāya) with 4 sections (pāda) each.",
            "structure": {
                "adhyayas": 8,
                "padas_per_adhyaya": 4,
                "total_padas": 32,
            },
            "note": "Full sutra database to be populated.",
        }, indent=2, ensure_ascii=False)

    return json.dumps({
        "title": data.get("title", "Aṣṭādhyāyī"),
        "author": data.get("author", "Pāṇini"),
        "description": data.get("description", "The foundational text of Sanskrit grammar"),
        "structure": data.get("structure", {}),
        "total_sutras": data.get("total_sutras", 0),
    }, indent=2, ensure_ascii=False)


def _get_sutras_section(adhyaya: int, pada: int) -> str:
    """Get sutras for a specific section."""
    data = _load_yaml("sutras.yaml")
    adhyayas = data.get("adhyayas", {})

    adhyaya_key = str(adhyaya)
    if adhyaya_key not in adhyayas:
        return json.dumps({
            "adhyaya": adhyaya,
            "pada": pada,
            "sutras": [],
            "note": f"No sutras found for adhyāya {adhyaya}",
        }, indent=2, ensure_ascii=False)

    padas = adhyayas[adhyaya_key].get("padas", {})
    pada_key = str(pada)

    if pada_key not in padas:
        return json.dumps({
            "adhyaya": adhyaya,
            "pada": pada,
            "sutras": [],
            "note": f"No sutras found for adhyāya {adhyaya}, pāda {pada}",
        }, indent=2, ensure_ascii=False)

    return json.dumps({
        "adhyaya": adhyaya,
        "pada": pada,
        "sutras": padas[pada_key],
    }, indent=2, ensure_ascii=False)


def _search_sutras(query: str) -> str:
    """Search sutras by topic."""
    if not query:
        return json.dumps({"error": "Search query is required"})

    data = _load_yaml("sutras.yaml")
    results: list[dict[str, Any]] = []

    for adhyaya_num, adhyaya_data in data.get("adhyayas", {}).items():
        for pada_num, sutras in adhyaya_data.get("padas", {}).items():
            for sutra in sutras:
                if (
                    query.lower() in sutra.get("text", "").lower()
                    or query.lower() in sutra.get("meaning", "").lower()
                    or query.lower() in sutra.get("transliteration", "").lower()
                ):
                    results.append({
                        "reference": f"{adhyaya_num}.{pada_num}.{sutra.get('number', '?')}",
                        **sutra,
                    })

    return json.dumps({
        "query": query,
        "results": results,
        "count": len(results),
    }, indent=2, ensure_ascii=False)
