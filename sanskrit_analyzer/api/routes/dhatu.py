"""Dhatu (verbal root) API endpoints, backed by the Dhātupāṭha.

Roots come from the bundled Dhātupāṭha CSVs (~2,250 entries, gaṇa and artha
per entry). Conjugated forms are not stored: they are derived on demand by
``vidyut.prakriya``, so any root can be conjugated in any lakāra.
"""

from enum import Enum
from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, Field
from starlette.concurrency import run_in_threadpool

from sanskrit_analyzer.dhatu import conjugation
from sanskrit_analyzer.dhatu.dhatupatha import entry_to_dict, get_dhatu_kosha

router = APIRouter(prefix="/api/v1/dhatu", tags=["Dhatu"])


class SearchType(str, Enum):
    """Type of dhatu search."""

    DHATU = "dhatu"  # Match the root form only
    MEANING = "meaning"  # Match the artha (Sanskrit gloss)
    ALL = "all"  # Match either


class DhatuSearchRequest(BaseModel):
    """Request model for dhatu search."""

    query: str = Field(..., description="Search query", min_length=1)
    search_type: SearchType = Field(
        default=SearchType.ALL,
        description="Type of search to perform",
    )
    limit: int = Field(default=20, ge=1, le=100, description="Maximum results")


class ConjugationResponse(BaseModel):
    """One (pada, puruṣa, vacana) slot of a conjugation table."""

    lakara: str
    pada: str
    purusha: str
    vacana: str
    forms_slp1: list[str]
    forms_devanagari: list[str]
    forms_iast: list[str]


class DhatuResponse(BaseModel):
    """One Dhātupāṭha entry."""

    code: str = Field(..., description="Dhātupāṭha code, e.g. 01.1137")
    root_slp1: str
    root_iast: str
    root_devanagari: str
    upadesha_slp1: str = Field(..., description="Citation form, with it-markers")
    upadesha_iast: str
    upadesha_devanagari: str
    gana: int
    gana_name: str
    artha_slp1: str | None = Field(None, description="Sanskrit gloss from the Dhātupāṭha")
    artha_iast: str | None = None
    artha_devanagari: str | None = None
    curated: bool = Field(False, description="Root reading is hand-curated, not heuristic")
    padas: list[str] = Field(default=[], description="Padas the root forms (derived)")
    conjugations: list[ConjugationResponse] = []


class DhatuListResponse(BaseModel):
    """Response for a list of dhatus."""

    count: int
    dhatus: list[DhatuResponse]


class GanaStatsResponse(BaseModel):
    """Response for gana statistics."""

    total_dhatus: int
    gana_counts: dict[int, int]


def _to_response(entry: dict[str, Any], **extra: Any) -> DhatuResponse:
    return DhatuResponse(**entry_to_dict(entry), **extra)


@router.get("/stats", response_model=GanaStatsResponse)
async def get_dhatu_stats(request: Request) -> GanaStatsResponse:
    """Get Dhātupāṭha statistics.

    Returns total count and breakdown by gaṇa (verb class).
    """
    kosha = get_dhatu_kosha()
    return GanaStatsResponse(total_dhatus=kosha.count(), gana_counts=kosha.gana_stats())


@router.get("/gana/{gana}", response_model=DhatuListResponse)
async def get_dhatus_by_gana(
    request: Request,
    gana: int,
    limit: int = Query(default=100, ge=1, le=500, description="Maximum results"),
) -> DhatuListResponse:
    """Get dhatus in a specific gaṇa (verb class).

    Gana ranges from 1-10, corresponding to the 10 Sanskrit verb classes.
    """
    if not 1 <= gana <= 10:
        raise HTTPException(status_code=400, detail="Gana must be between 1 and 10")

    entries = await run_in_threadpool(get_dhatu_kosha().by_gana, gana)
    dhatus = [_to_response(e) for e in entries[:limit]]
    return DhatuListResponse(count=len(dhatus), dhatus=dhatus)


@router.post("/search", response_model=DhatuListResponse)
async def search_dhatus(
    request: Request,
    body: DhatuSearchRequest,
) -> DhatuListResponse:
    """Search the Dhātupāṭha.

    Supports searching by:
    - dhatu: match the root form (Devanagari, IAST or SLP1)
    - meaning: match the artha, the Sanskrit gloss carried by the Dhātupāṭha
    - all: match either
    """
    kosha = get_dhatu_kosha()
    if body.search_type == SearchType.DHATU:
        entries = (await run_in_threadpool(kosha.find, body.query))[: body.limit]
    else:
        artha_only = body.search_type == SearchType.MEANING
        entries = await run_in_threadpool(kosha.search, body.query, body.limit, artha_only)

    dhatus = [_to_response(e) for e in entries]
    return DhatuListResponse(count=len(dhatus), dhatus=dhatus)


@router.get("/{dhatu}", response_model=DhatuListResponse)
async def get_dhatu(
    request: Request,
    dhatu: str,
    include_conjugations: bool = Query(
        default=False,
        description="Derive conjugation forms (needs the vidyut data bundle)",
    ),
    lakara: str = Query(
        default="lat",
        description=f"Lakāra to conjugate; one of {', '.join(conjugation.LAKARA_NAMES)}",
    ),
) -> DhatuListResponse:
    """Look up a dhatu by its root form.

    Accepts Devanagari (गम्), IAST (gam), SLP1 (BU), or the Dhātupāṭha
    citation form (ḍukṛñ). A root may have several Dhātupāṭha entries — √kṛ is
    in both the 5th and 8th gaṇa — so the response is a list.
    """
    entries = await run_in_threadpool(get_dhatu_kosha().find, dhatu)
    if not entries:
        raise HTTPException(status_code=404, detail=f"Dhatu not found: {dhatu}")

    if not include_conjugations:
        return DhatuListResponse(
            count=len(entries), dhatus=[_to_response(e) for e in entries]
        )

    if conjugation.normalize_lakara(lakara) is None:
        raise HTTPException(status_code=400, detail=f"Unknown lakara: {lakara}")
    if not conjugation.is_available():
        raise HTTPException(
            status_code=503,
            detail="Conjugation needs the vidyut data bundle, which is not installed",
        )

    dhatus = []
    for entry in entries:
        rows = await run_in_threadpool(conjugation.conjugate, entry["code"], lakara)
        dhatus.append(
            _to_response(
                entry,
                padas=sorted({r["pada"] for r in rows}),
                conjugations=[ConjugationResponse(**r) for r in rows],
            )
        )
    return DhatuListResponse(count=len(dhatus), dhatus=dhatus)
