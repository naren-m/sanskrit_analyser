"""Dhatu resource provider for MCP server."""

import json
from typing import Any

from mcp.server import Server
from mcp.types import Resource

from sanskrit_analyzer.data.dhatu_db import DhatuDB, DhatuEntry


def _dhatu_to_dict(entry: DhatuEntry) -> dict[str, Any]:
    """Convert DhatuEntry to dictionary."""
    return {
        "id": entry.id,
        "dhatu_devanagari": entry.dhatu_devanagari,
        "dhatu_iast": entry.dhatu_iast,
        "meaning_english": entry.meaning_english,
        "meaning_hindi": entry.meaning_hindi,
        "gana": entry.gana,
        "pada": entry.pada,
        "panini_reference": entry.panini_reference,
    }


def register_dhatu_resources(server: Server) -> None:
    """Register dhatu resources with the MCP server.

    Args:
        server: MCP server instance.
    """
    db = DhatuDB()

    @server.list_resources()
    async def list_resources() -> list[Resource]:
        return [
            Resource(
                uri="dhatu://overview",  # type: ignore[arg-type]
                name="Dhatu Overview",
                description="Overview of the dhatu database including total count and gana distribution",
                mimeType="application/json",
            ),
            Resource(
                uri="dhatu://gana/1",  # type: ignore[arg-type]
                name="Gana 1 Dhatus (bhvādi)",
                description="Dhatus in the first verb class (bhvādi-gaṇa)",
                mimeType="application/json",
            ),
            Resource(
                uri="dhatu://gana/2",  # type: ignore[arg-type]
                name="Gana 2 Dhatus (adādi)",
                description="Dhatus in the second verb class (adādi-gaṇa)",
                mimeType="application/json",
            ),
            Resource(
                uri="dhatu://gana/3",  # type: ignore[arg-type]
                name="Gana 3 Dhatus (juhotyādi)",
                description="Dhatus in the third verb class (juhotyādi-gaṇa)",
                mimeType="application/json",
            ),
            Resource(
                uri="dhatu://gana/4",  # type: ignore[arg-type]
                name="Gana 4 Dhatus (divādi)",
                description="Dhatus in the fourth verb class (divādi-gaṇa)",
                mimeType="application/json",
            ),
            Resource(
                uri="dhatu://gana/5",  # type: ignore[arg-type]
                name="Gana 5 Dhatus (svādi)",
                description="Dhatus in the fifth verb class (svādi-gaṇa)",
                mimeType="application/json",
            ),
            Resource(
                uri="dhatu://gana/6",  # type: ignore[arg-type]
                name="Gana 6 Dhatus (tudādi)",
                description="Dhatus in the sixth verb class (tudādi-gaṇa)",
                mimeType="application/json",
            ),
            Resource(
                uri="dhatu://gana/7",  # type: ignore[arg-type]
                name="Gana 7 Dhatus (rudhādi)",
                description="Dhatus in the seventh verb class (rudhādi-gaṇa)",
                mimeType="application/json",
            ),
            Resource(
                uri="dhatu://gana/8",  # type: ignore[arg-type]
                name="Gana 8 Dhatus (tanādi)",
                description="Dhatus in the eighth verb class (tanādi-gaṇa)",
                mimeType="application/json",
            ),
            Resource(
                uri="dhatu://gana/9",  # type: ignore[arg-type]
                name="Gana 9 Dhatus (kryādi)",
                description="Dhatus in the ninth verb class (kryādi-gaṇa)",
                mimeType="application/json",
            ),
            Resource(
                uri="dhatu://gana/10",  # type: ignore[arg-type]
                name="Gana 10 Dhatus (curādi)",
                description="Dhatus in the tenth verb class (curādi-gaṇa)",
                mimeType="application/json",
            ),
        ]

    @server.read_resource()
    async def read_resource(uri: str) -> str:
        if uri == "dhatu://overview":
            return _get_overview(db)
        elif uri.startswith("dhatu://gana/"):
            gana_str = uri.replace("dhatu://gana/", "")
            try:
                gana = int(gana_str)
                return _get_gana_dhatus(db, gana)
            except ValueError:
                return json.dumps({"error": f"Invalid gana number: {gana_str}"})
        elif uri.startswith("dhatu://"):
            dhatu_name = uri.replace("dhatu://", "")
            if "/conjugations" in dhatu_name:
                dhatu_name = dhatu_name.replace("/conjugations", "")
                return _get_dhatu_conjugations(db, dhatu_name)
            else:
                return _get_dhatu_entry(db, dhatu_name)
        else:
            return json.dumps({"error": f"Unknown resource: {uri}"})


def _get_overview(db: DhatuDB) -> str:
    """Get overview of dhatu database."""
    gana_distribution: dict[int, int] = {}
    total = 0

    for gana in range(1, 11):
        entries = db.get_by_gana(gana, limit=1000)
        count = len(entries)
        gana_distribution[gana] = count
        total += count

    gana_names = {
        1: "bhvādi (भ्वादि)",
        2: "adādi (अदादि)",
        3: "juhotyādi (जुहोत्यादि)",
        4: "divādi (दिवादि)",
        5: "svādi (स्वादि)",
        6: "tudādi (तुदादि)",
        7: "rudhādi (रुधादि)",
        8: "tanādi (तनादि)",
        9: "kryādi (क्र्यादि)",
        10: "curādi (चुरादि)",
    }

    overview = {
        "total_dhatus": total,
        "gana_distribution": [
            {
                "gana": gana,
                "name": gana_names[gana],
                "count": gana_distribution[gana],
            }
            for gana in range(1, 11)
        ],
        "description": "The dhatu database contains Sanskrit verbal roots organized by their gaṇa (verb class). "
        "Each gaṇa has characteristic conjugation patterns based on the first dhatu of the class.",
    }

    return json.dumps(overview, indent=2, ensure_ascii=False)


def _get_gana_dhatus(db: DhatuDB, gana: int) -> str:
    """Get dhatus in a specific gana."""
    if not 1 <= gana <= 10:
        return json.dumps({"error": "Gana must be between 1 and 10"})

    entries = db.get_by_gana(gana, limit=100)

    result = {
        "gana": gana,
        "count": len(entries),
        "dhatus": [_dhatu_to_dict(entry) for entry in entries],
    }

    return json.dumps(result, indent=2, ensure_ascii=False)


def _get_dhatu_entry(db: DhatuDB, dhatu: str) -> str:
    """Get a specific dhatu entry."""
    entry = db.lookup_by_dhatu(dhatu)

    if not entry:
        return json.dumps({"error": f"Dhatu not found: {dhatu}"})

    return json.dumps(_dhatu_to_dict(entry), indent=2, ensure_ascii=False)


def _get_dhatu_conjugations(db: DhatuDB, dhatu: str) -> str:
    """Get conjugation tables for a dhatu."""
    entry = db.lookup_by_dhatu(dhatu)

    if not entry:
        return json.dumps({"error": f"Dhatu not found: {dhatu}"})

    lakaras = ["lat", "lit", "lut", "lrt", "lot", "lan", "lin", "lun", "lrn"]
    conjugations: dict[str, Any] = {
        "dhatu": _dhatu_to_dict(entry),
        "conjugations": {},
    }

    for lakara in lakaras:
        forms = db.get_conjugation(entry.id, lakara)
        if forms:
            conjugations["conjugations"][lakara] = [
                {
                    "purusha": f.purusha,
                    "vacana": f.vacana,
                    "pada": f.pada,
                    "form_devanagari": f.form_devanagari,
                    "form_iast": f.form_iast,
                }
                for f in forms
            ]

    return json.dumps(conjugations, indent=2, ensure_ascii=False)
