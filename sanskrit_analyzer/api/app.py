"""FastAPI application factory and configuration."""

import os
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from sanskrit_analyzer import __version__
from sanskrit_analyzer.analyzer import Analyzer
from sanskrit_analyzer.config import Config

# Localhost dev origins used when no explicit allowlist is configured.
_DEFAULT_CORS_ORIGINS = [
    "http://localhost:3000",
    "http://localhost:8000",
    "http://127.0.0.1:3000",
    "http://127.0.0.1:8000",
]


def _resolve_cors_origins() -> list[str]:
    """Resolve CORS origins from the ``SANSKRIT_CORS_ORIGINS`` env var.

    The value is a comma-separated list of origins. When unset, a safe set of
    localhost development origins is used instead of a wildcard so that
    credentialed cross-origin requests remain restricted to known hosts.
    """
    raw = os.environ.get("SANSKRIT_CORS_ORIGINS")
    if raw:
        origins = [o.strip() for o in raw.split(",") if o.strip()]
        if origins:
            return origins
    return list(_DEFAULT_CORS_ORIGINS)


def create_app(
    config: Config | None = None,
    cors_origins: list[str] | None = None,
) -> FastAPI:
    """Create and configure the FastAPI application.

    Args:
        config: Application configuration. If None, loads from default location.
        cors_origins: List of allowed CORS origins. When None, origins are read
            from the ``SANSKRIT_CORS_ORIGINS`` env var, defaulting to localhost
            dev origins.

    Returns:
        Configured FastAPI application instance.
    """
    if config is None:
        config = Config.load()

    if cors_origins is None:
        cors_origins = _resolve_cors_origins()

    # Create analyzer instance to be shared across requests
    analyzer = Analyzer(config)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        """Application lifespan handler for startup/shutdown."""
        # Startup: initialize the analyzer
        await analyzer._initialize()
        app.state.analyzer = analyzer
        app.state.config = config
        yield
        # Shutdown: cleanup resources
        if analyzer._cache:
            if hasattr(analyzer._cache, "_redis") and analyzer._cache._redis:
                await analyzer._cache._redis.close()

    app = FastAPI(
        title="Sanskrit Analyzer API",
        description=(
            "REST API for analyzing Sanskrit text with 3-engine ensemble analysis. "
            "Provides morphological analysis, sandhi splitting, and dhatu lookups."
        ),
        version=__version__,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        lifespan=lifespan,
    )

    # Add CORS middleware. Credentials are only permitted with an explicit
    # origin allowlist; combining a "*" wildcard with credentials is unsafe
    # (and rejected by browsers), so credentials are disabled in that case.
    allow_credentials = "*" not in cors_origins
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_credentials=allow_credentials,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Register routers
    _register_routes(app)

    # Observability via shared homelab-observability lib.
    # OTLP endpoint, sampler, Loki endpoint, etc. come from HOMELAB_* env vars
    # set by the homelab-observability Kustomize component at deploy time.
    # Skipped if the lib isn't installed (e.g. dev shells without [api] extras).
    _setup_observability(app)

    return app


def _setup_observability(app: FastAPI) -> None:
    """Wire OpenTelemetry tracing + metrics + logs via homelab-observability.

    No-op when the lib (or its FastAPI instrumentor) isn't installed; that
    lets dev shells run without pulling the full observability stack.
    """
    try:
        import homelab_observability as hobs
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
    except ImportError:
        return
    hobs.setup(service_name="sanskrit-analyzer", service_version=__version__)
    FastAPIInstrumentor.instrument_app(app)


def _register_routes(app: FastAPI) -> None:
    """Register all API routes."""
    from sanskrit_analyzer.api.routes import analyze, dhatu, health

    app.include_router(health.router, tags=["Health"])
    app.include_router(analyze.router)
    app.include_router(dhatu.router)


# Default app instance for uvicorn
app = create_app()
