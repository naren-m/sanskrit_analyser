"""Response helpers for MCP tools."""

import json
from typing import Any

from mcp.types import TextContent


def text_response(content: str) -> list[TextContent]:
    """Create a single text response.

    Args:
        content: Text content to return.

    Returns:
        List containing single TextContent.
    """
    return [TextContent(type="text", text=content)]


def json_response(data: Any) -> list[TextContent]:
    """Create a JSON text response.

    Args:
        data: Data to serialize as JSON.

    Returns:
        List containing single TextContent with formatted JSON.
    """
    return [TextContent(type="text", text=json.dumps(data, indent=2, ensure_ascii=False))]


def error_response(message: str) -> list[TextContent]:
    """Create an error text response.

    Args:
        message: Error message.

    Returns:
        List containing single TextContent with error prefix.
    """
    return [TextContent(type="text", text=f"Error: {message}")]
