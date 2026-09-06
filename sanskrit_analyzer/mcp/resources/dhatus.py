"""Dhatu resource provider for MCP server."""

import json
from collections.abc import Awaitable, Callable
from typing import Any

from mcp.types import Resource

from sanskrit_analyzer.dhatu import conjugation
from sanskrit_analyzer.dhatu.dhatupatha import DhatuKosha, entry_to_dict, get_dhatu_kosha

# A reader returns the resource body, or None if it does not own ``uri``
# (so the server can try the next resource group).
ResourceReader = Callable[[str], Awaitable[str | None]]

#: The ten gaṇas (verb classes), IAST and Devanagari, named after their first
#: root: gaṇa 1 is bhvādi because it opens with √bhū.
_GANA_NAMES = {
    1: ("bhvādi", "भ्वादि"),
    2: ("adādi", "अदादि"),
    3: ("juhotyādi", "जुहोत्यादि"),
    4: ("divādi", "दिवादि"),
    5: ("svādi", "स्वादि"),
    6: ("tudādi", "तुदादि"),
    7: ("rudhādi", "रुधादि"),
    8: ("tanādi", "तनादि"),
    9: ("kryādi", "क्र्यादि"),
    10: ("curādi", "चुरादि"),
}


def _json(payload: Any) -> str:
    return json.dumps(payload, indent=2, ensure_ascii=False)


def build_dhatu_resources() -> tuple[list[Resource], ResourceReader]:
    """Build the dhatu resource specs and their reader.

    The MCP ``Server`` keeps only one ``list_resources``/``read_resource``
    handler, so each resource group exposes its specs/reader for the server to
    aggregate rather than registering its own (which would overwrite the others).
    """
    kosha = get_dhatu_kosha()

    resources = [
        Resource(
            uri="dhatu://overview",  # type: ignore[arg-type]
            name="Dhatu Overview",
            description="Overview of the Dhatupatha: total count and gana distribution",
            mimeType="application/json",
        ),
        *(
            Resource(
                uri=f"dhatu://gana/{gana}",  # type: ignore[arg-type]
                name=f"Gana {gana} Dhatus ({iast})",
                description=f"Dhatus in verb class {gana} ({iast}-gaṇa)",
                mimeType="application/json",
            )
            for gana, (iast, _deva) in _GANA_NAMES.items()
        ),
    ]

    async def read_resource(uri: str) -> str | None:
        uri = str(uri)
        if uri == "dhatu://overview":
            return _get_overview(kosha)
        if uri.startswith("dhatu://gana/"):
            gana = uri.removeprefix("dhatu://gana/")
            if not gana.isdigit():
                return _json({"error": f"Invalid gana number: {gana}"})
            return _get_gana_dhatus(kosha, int(gana))
        if uri.startswith("dhatu://"):
            name = uri.removeprefix("dhatu://")
            if name.endswith("/conjugations"):
                return _get_dhatu_conjugations(kosha, name.removesuffix("/conjugations"))
            return _get_dhatu_entry(kosha, name)
        return None

    return resources, read_resource


def _get_overview(kosha: DhatuKosha) -> str:
    """Get overview of the Dhatupatha."""
    counts = kosha.gana_stats()
    return _json(
        {
            "total_dhatus": kosha.count(),
            "gana_distribution": [
                {"gana": gana, "name": f"{iast} ({deva})", "count": counts.get(gana, 0)}
                for gana, (iast, deva) in _GANA_NAMES.items()
            ],
            "description": (
                "The Dhātupāṭha lists Sanskrit verbal roots organized by their gaṇa "
                "(verb class). Each gaṇa has characteristic conjugation patterns based "
                "on the first dhatu of the class. Conjugated forms are derived on "
                "demand by the Pāṇinian engine, not stored."
            ),
        }
    )


def _get_gana_dhatus(kosha: DhatuKosha, gana: int) -> str:
    """Get dhatus in a specific gana."""
    if gana not in _GANA_NAMES:
        return _json({"error": "Gana must be between 1 and 10"})

    entries = kosha.by_gana(gana)[:100]
    return _json(
        {
            "gana": gana,
            "count": len(entries),
            "dhatus": [entry_to_dict(entry) for entry in entries],
        }
    )


def _get_dhatu_entry(kosha: DhatuKosha, dhatu: str) -> str:
    """Get the Dhatupatha entries for a root."""
    entries = kosha.find(dhatu)

    if not entries:
        return _json({"error": f"Dhatu not found: {dhatu}"})

    return _json([entry_to_dict(entry) for entry in entries])


def _get_dhatu_conjugations(kosha: DhatuKosha, dhatu: str) -> str:
    """Derive the conjugation tables for a root, one per lakara."""
    entries = kosha.find(dhatu)

    if not entries:
        return _json({"error": f"Dhatu not found: {dhatu}"})
    if not conjugation.is_available():
        return _json(
            {"error": "conjugation needs the vidyut data bundle, which is not installed"}
        )

    result = []
    for entry in entries:
        tables = {
            lakara: forms
            for lakara in conjugation.LAKARA_NAMES
            if (forms := conjugation.conjugate(entry["code"], lakara))
        }
        result.append({"dhatu": entry_to_dict(entry), "conjugations": tables})

    return _json(result)
