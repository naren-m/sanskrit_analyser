"""FastAPI application factory and configuration."""

from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from sanskrit_analyzer import __version__
from sanskrit_analyzer.analyzer import Analyzer
from sanskrit_analyzer.config import Config


def create_app(
    config: Config | None = None,
    cors_origins: list[str] | None = None,
) -> FastAPI:
    """Create and configure the FastAPI application.

    Args:
        config: Application configuration. If None, loads from default location.
        cors_origins: List of allowed CORS origins. Defaults to ["*"] in development.

    Returns:
        Configured FastAPI application instance.
    """
    if config is None:
        config = Config.load()

    if cors_origins is None:
        cors_origins = ["*"]  # Permissive for development

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

    # Add CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Register routers
    _register_routes(app)

    return app


def _register_routes(app: FastAPI) -> None:
    """Register all API routes."""
    from sanskrit_analyzer.api.routes import analyze, health

    app.include_router(health.router, tags=["Health"])
    app.include_router(analyze.router)


# Default app instance for uvicorn
app = create_app()
