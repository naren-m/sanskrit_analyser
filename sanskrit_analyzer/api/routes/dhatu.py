"""Dhatu (verbal root) API endpoints."""

from enum import Enum
from typing import TYPE_CHECKING

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from sanskrit_analyzer.data.dhatu_db import DhatuEntry

router = APIRouter(prefix="/api/v1/dhatu", tags=["Dhatu"])


class SearchType(str, Enum):
    """Type of dhatu search."""

    DHATU = "dhatu"  # Search by dhatu form
    MEANING = "meaning"  # Search by English meaning
    ALL = "all"  # Search all fields


class DhatuSearchRequest(BaseModel):
    """Request model for dhatu search."""

    query: str = Field(..., description="Search query", min_length=1)
    search_type: SearchType = Field(
        default=SearchType.ALL,
        description="Type of search to perform",
    )
    limit: int = Field(default=20, ge=1, le=100, description="Maximum results")


class ConjugationResponse(BaseModel):
    """Single conjugation form response."""

    lakara: str
    purusha: str
    vacana: str
    pada: str
    form_devanagari: str
    form_iast: str | None = None


class DhatuResponse(BaseModel):
    """Dhatu information response."""

    id: int
    dhatu_devanagari: str
    dhatu_iast: str | None = None
    meaning_english: str | None = None
    meaning_hindi: str | None = None
    gana: int | None = None
    pada: str | None = None
    it_category: str | None = None
    panini_reference: str | None = None
    examples: str | None = None
    synonyms: str | None = None
    related_words: str | None = None
    conjugations: list[ConjugationResponse] = []


class DhatuListResponse(BaseModel):
    """Response for list of dhatus."""

    count: int
    dhatus: list[DhatuResponse]


class GanaStatsResponse(BaseModel):
    """Response for gana statistics."""

    total_dhatus: int
    gana_counts: dict[int, int]


def _entry_to_response(entry: "DhatuEntry") -> DhatuResponse:
    """Convert DhatuEntry to response model."""
    conjugations = [
        ConjugationResponse(
            lakara=c.lakara,
            purusha=c.purusha,
            vacana=c.vacana,
            pada=c.pada,
            form_devanagari=c.form_devanagari,
            form_iast=c.form_iast,
        )
        for c in entry.conjugations
    ]

    return DhatuResponse(
        id=entry.id,
        dhatu_devanagari=entry.dhatu_devanagari,
        dhatu_iast=entry.dhatu_iast,
        meaning_english=entry.meaning_english,
        meaning_hindi=entry.meaning_hindi,
        gana=entry.gana,
        pada=entry.pada,
        it_category=entry.it_category,
        panini_reference=entry.panini_reference,
        examples=entry.examples,
        synonyms=entry.synonyms,
        related_words=entry.related_words,
        conjugations=conjugations,
    )


@router.get("/stats", response_model=GanaStatsResponse)
async def get_dhatu_stats(request: Request) -> GanaStatsResponse:
    """Get dhatu database statistics.

    Returns total count and breakdown by gana (verb class).
    """
    from sanskrit_analyzer.data.dhatu_db import DhatuDB

    db = DhatuDB()
    try:
        total = db.count()
        gana_counts = db.get_gana_stats()
        return GanaStatsResponse(total_dhatus=total, gana_counts=gana_counts)
    finally:
        db.close()


@router.get("/gana/{gana}", response_model=DhatuListResponse)
async def get_dhatus_by_gana(
    request: Request,
    gana: int,
    limit: int = Query(default=100, ge=1, le=500, description="Maximum results"),
) -> DhatuListResponse:
    """Get all dhatus in a specific gana (verb class).

    Gana ranges from 1-10, corresponding to the 10 Sanskrit verb classes.
    """
    if not 1 <= gana <= 10:
        raise HTTPException(status_code=400, detail="Gana must be between 1 and 10")

    from sanskrit_analyzer.data.dhatu_db import DhatuDB

    db = DhatuDB()
    try:
        entries = db.get_by_gana(gana, limit=limit)
        dhatus = [_entry_to_response(e) for e in entries]
        return DhatuListResponse(count=len(dhatus), dhatus=dhatus)
    finally:
        db.close()


@router.post("/search", response_model=DhatuListResponse)
async def search_dhatus(
    request: Request,
    body: DhatuSearchRequest,
) -> DhatuListResponse:
    """Search for dhatus.

    Supports searching by:
    - dhatu: Match dhatu form (Devanagari, IAST, or transliterated)
    - meaning: Match English meaning
    - all: Search all fields
    """
    from sanskrit_analyzer.data.dhatu_db import DhatuDB

    db = DhatuDB()
    try:
        if body.search_type == SearchType.DHATU:
            # Try exact lookup first
            entry = db.lookup_by_dhatu(body.query)
            if entry:
                return DhatuListResponse(count=1, dhatus=[_entry_to_response(entry)])
            # Fall back to search
            entries = db.search(body.query, limit=body.limit)
        elif body.search_type == SearchType.MEANING:
            entries = db.lookup_by_meaning(body.query, limit=body.limit)
        else:  # ALL
            entries = db.search(body.query, limit=body.limit)

        dhatus = [_entry_to_response(e) for e in entries]
        return DhatuListResponse(count=len(dhatus), dhatus=dhatus)
    finally:
        db.close()


@router.get("/{dhatu}", response_model=DhatuResponse)
async def get_dhatu(
    request: Request,
    dhatu: str,
    include_conjugations: bool = Query(
        default=False,
        description="Include conjugation forms",
    ),
) -> DhatuResponse:
    """Look up a specific dhatu by its form.

    Accepts dhatu in Devanagari (e.g., गम्), IAST (e.g., gam), or
    transliterated form.
    """
    from sanskrit_analyzer.data.dhatu_db import DhatuDB

    db = DhatuDB()
    try:
        entry = db.lookup_by_dhatu(dhatu, include_conjugations=include_conjugations)
        if entry is None:
            raise HTTPException(status_code=404, detail=f"Dhatu not found: {dhatu}")
        return _entry_to_response(entry)
    finally:
        db.close()
