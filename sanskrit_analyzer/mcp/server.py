"""MCP server implementation for Sanskrit Analyzer."""

import argparse
from typing import Any

from mcp.server.fastmcp import FastMCP

from sanskrit_analyzer.config import Config, MCPServerConfig

# Global server instance for tool registration
_server: FastMCP | None = None


def create_server(config: MCPServerConfig | None = None) -> FastMCP:
    """Create and configure the MCP server.

    Args:
        config: MCP server configuration. Uses defaults from Config if not provided.
    """
    global _server

    if config is None:
        config = Config().mcp

    _server = FastMCP(
        name="Sanskrit Analyzer",
        instructions="Sanskrit text analysis with morphology, dhatu lookup, and grammar tools",
        host=config.host,
        port=config.port,
    )

    # Register tools
    _register_tools(_server)

    return _server


def _register_tools(server: FastMCP) -> None:
    """Register all MCP tools with the server."""
    from sanskrit_analyzer.mcp.tools.analysis import (
        analyze_sentence as _analyze,
        get_morphology as _morph,
        split_sandhi as _split,
        transliterate as _translit,
    )
    from sanskrit_analyzer.mcp.tools.dhatu import (
        conjugate_verb as _conjugate,
        list_gana as _list_gana,
        lookup_dhatu as _lookup,
        search_dhatu as _search,
    )
    from sanskrit_analyzer.mcp.tools.grammar import (
        explain_parse as _explain,
        get_pratyaya as _pratyaya,
        identify_compound as _compound,
        resolve_ambiguity as _resolve,
    )

    @server.tool()
    async def analyze_sentence(
        text: str,
        mode: str | None = None,
        verbosity: str | None = None,
    ) -> dict[str, Any]:
        """Analyze a Sanskrit sentence and return full morphological breakdown.

        Args:
            text: Sanskrit text to analyze (Devanagari, IAST, or SLP1).
            mode: Analysis mode - 'educational', 'production', or 'academic'.
            verbosity: Response detail level - 'minimal', 'standard', or 'detailed'.

        Returns:
            Analysis result with sandhi_groups, words, morphology, and confidence.
        """
        return await _analyze(text, mode, verbosity)

    @server.tool()
    async def split_sandhi(
        text: str,
        verbosity: str | None = None,
    ) -> dict[str, Any]:
        """Split Sanskrit text at sandhi boundaries.

        Lighter weight than full analysis - returns sandhi groups with split words
        and optionally the sandhi rules applied.

        Args:
            text: Sanskrit text to split (Devanagari, IAST, or SLP1).
            verbosity: Response detail level - 'minimal', 'standard', or 'detailed'.

        Returns:
            Sandhi splits with surface forms, component words, and rules.
        """
        return await _split(text, verbosity)

    @server.tool()
    async def get_morphology(
        word: str,
        context: str | None = None,
        verbosity: str | None = None,
    ) -> dict[str, Any]:
        """Get morphological tags for a Sanskrit word.

        Returns case, gender, number, person, tense, mood, voice as applicable.

        Args:
            word: Sanskrit word to analyze (Devanagari, IAST, or SLP1).
            context: Optional sentence context for disambiguation.
            verbosity: Response detail level - 'minimal', 'standard', or 'detailed'.

        Returns:
            Morphological analysis with tags, meanings, and alternatives.
        """
        return await _morph(word, context, verbosity)

    @server.tool()
    def transliterate(
        text: str,
        from_script: str,
        to_script: str,
    ) -> dict[str, Any]:
        """Convert Sanskrit text between different scripts.

        Args:
            text: Sanskrit text to convert.
            from_script: Source script (devanagari, iast, slp1, itrans).
            to_script: Target script (devanagari, iast, slp1, itrans).

        Returns:
            Converted text with original and result.
        """
        return _translit(text, from_script, to_script)

    # Dhatu tools
    @server.tool()
    def lookup_dhatu(
        dhatu: str,
        include_conjugations: bool = False,
        verbosity: str | None = None,
    ) -> dict[str, Any]:
        """Look up a dhatu (verbal root) by its form.

        Args:
            dhatu: The verbal root (Devanagari or IAST).
            include_conjugations: Whether to include conjugation tables.
            verbosity: Response detail level - 'minimal', 'standard', or 'detailed'.

        Returns:
            Dhatu information with meaning, gana, pada, and optional conjugations.
        """
        return _lookup(dhatu, include_conjugations, verbosity)

    @server.tool()
    def search_dhatu(
        query: str,
        limit: int = 10,
        verbosity: str | None = None,
    ) -> dict[str, Any]:
        """Search dhatus by meaning or pattern.

        Args:
            query: Search query (matches dhatu, meaning, examples).
            limit: Maximum number of results (default 10).
            verbosity: Response detail level.

        Returns:
            List of matching dhatu entries.
        """
        return _search(query, limit, verbosity)

    @server.tool()
    def conjugate_verb(
        dhatu: str,
        lakara: str | None = None,
        purusha: str | None = None,
        vacana: str | None = None,
    ) -> dict[str, Any]:
        """Get conjugation forms for a dhatu.

        Args:
            dhatu: The verbal root (Devanagari or IAST).
            lakara: Tense/mood (lat, lit, lut, lrt, let, lot, lan, etc.).
            purusha: Person (prathama, madhyama, uttama).
            vacana: Number (ekavacana, dvivacana, bahuvacana).

        Returns:
            Conjugation forms matching the specified filters.
        """
        return _conjugate(dhatu, lakara, purusha, vacana)

    @server.tool()
    def list_gana(
        gana: int,
        limit: int = 20,
    ) -> dict[str, Any]:
        """List dhatus belonging to a verb class (gana).

        Args:
            gana: Verb class number (1-10).
            limit: Maximum number of results (default 20).

        Returns:
            List of dhatus in the specified gana with their meanings.
        """
        return _list_gana(gana, limit)

    # Grammar tools
    @server.tool()
    async def explain_parse(
        text: str,
        parse_indices: list[int] | None = None,
        verbosity: str | None = None,
    ) -> dict[str, Any]:
        """Compare multiple parse interpretations of Sanskrit text.

        Args:
            text: Sanskrit text to analyze.
            parse_indices: Optional list of parse indices to include (0-based).
            verbosity: Response detail level - 'minimal', 'standard', or 'detailed'.

        Returns:
            Parse comparisons with confidence scores and word breakdowns.
        """
        return await _explain(text, parse_indices, verbosity)

    @server.tool()
    async def identify_compound(
        word: str,
        verbosity: str | None = None,
    ) -> dict[str, Any]:
        """Identify compound type (samasa) in a Sanskrit word.

        Args:
            word: Sanskrit word to analyze (Devanagari or IAST).
            verbosity: Response detail level - 'minimal', 'standard', or 'detailed'.

        Returns:
            Compound analysis with type and components.
        """
        return await _compound(word, verbosity)

    @server.tool()
    async def get_pratyaya(
        word: str,
        verbosity: str | None = None,
    ) -> dict[str, Any]:
        """Identify suffixes (pratyayas) applied to a Sanskrit word.

        Args:
            word: Sanskrit word to analyze (Devanagari or IAST).
            verbosity: Response detail level - 'minimal', 'standard', or 'detailed'.

        Returns:
            List of identified suffixes with type and function.
        """
        return await _pratyaya(word, verbosity)

    @server.tool()
    async def resolve_ambiguity(
        text: str,
        context: str | None = None,
    ) -> dict[str, Any]:
        """Resolve ambiguous parses and return the most likely interpretation.

        Args:
            text: Sanskrit text to analyze.
            context: Optional sentence context for better disambiguation.

        Returns:
            Selected parse with confidence and reasoning.
        """
        return await _resolve(text, context)


def main() -> None:
    """Entry point for running the MCP server."""
    # Load config (includes env var overrides)
    app_config = Config.load(validate=False)
    mcp_config = app_config.mcp

    parser = argparse.ArgumentParser(description="Sanskrit Analyzer MCP Server")
    parser.add_argument(
        "--host",
        default=mcp_config.host,
        help=f"Host to bind to (default: {mcp_config.host})",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=mcp_config.port,
        help=f"Port to listen on (default: {mcp_config.port})",
    )
    parser.add_argument(
        "--transport",
        choices=["sse", "stdio"],
        default="sse",
        help="Transport protocol (default: sse)",
    )
    args = parser.parse_args()

    # Override config with CLI args
    mcp_config.host = args.host
    mcp_config.port = args.port

    server = create_server(config=mcp_config)
    server.run(transport=args.transport)


if __name__ == "__main__":
    main()
