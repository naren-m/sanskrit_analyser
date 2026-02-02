"""Health check endpoints."""

from fastapi import APIRouter, Request
from pydantic import BaseModel

router = APIRouter()


class HealthResponse(BaseModel):
    """Health check response model."""

    status: str
    version: str
    engines: list[str]
    cache_enabled: bool


class DetailedHealthResponse(BaseModel):
    """Detailed health check response."""

    status: str
    version: str
    engines: dict[str, bool]
    cache: dict[str, bool]
    disambiguation: dict[str, bool]


@router.get("/health", response_model=HealthResponse)
async def health_check(request: Request) -> HealthResponse:
    """Basic health check endpoint.

    Returns the API status, version, and available engines.
    """
    from sanskrit_analyzer import __version__

    analyzer = request.app.state.analyzer

    return HealthResponse(
        status="healthy",
        version=__version__,
        engines=analyzer.get_available_engines(),
        cache_enabled=analyzer._cache is not None,
    )


@router.get("/health/detailed", response_model=DetailedHealthResponse)
async def detailed_health_check(request: Request) -> DetailedHealthResponse:
    """Detailed health check with component status.

    Returns status of each engine, cache tier, and disambiguation component.
    """
    from sanskrit_analyzer import __version__

    analyzer = request.app.state.analyzer
    health = await analyzer.health_check()

    return DetailedHealthResponse(
        status="healthy",
        version=__version__,
        engines={
            "vidyut": health.get("engine_vidyut", False),
            "dharmamitra": health.get("engine_dharmamitra", False),
            "heritage": health.get("engine_heritage", False),
        },
        cache={
            "memory": health.get("cache_memory", False),
            "redis": health.get("cache_redis", False),
            "sqlite": health.get("cache_sqlite", False),
        },
        disambiguation={
            "rules": health.get("disambiguation_rules", False),
            "llm": health.get("disambiguation_llm", False),
        },
    )
