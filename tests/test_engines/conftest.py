"""Shared pytest configuration for engine tests."""


def pytest_configure(config: object) -> None:
    """Register custom markers used by the engine test suite."""
    config.addinivalue_line(  # type: ignore[attr-defined]
        "markers",
        "network: marks tests that hit a live external service "
        "(deselected by default; run explicitly with '-m network')",
    )
