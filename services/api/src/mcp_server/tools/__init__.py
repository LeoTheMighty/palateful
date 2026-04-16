"""MCP tool registration.

Each module in this package decorates functions with `@mcp.tool()` as side
effects of being imported. `register_all_tools()` imports them all exactly
once, making the tool registry idempotent and import-order-safe.
"""

from __future__ import annotations

_REGISTERED = False


def register_all_tools() -> None:
    """Import every tool module so its `@mcp.tool()` decorators run."""
    global _REGISTERED
    if _REGISTERED:
        return

    # Importing the modules is what triggers @mcp.tool() registration.
    from mcp_server.tools import (  # noqa: F401
        agent_tools,
        import_tools,
        meal_planning,
        recipe_books,
        recipes,
        search,
        shopping,
        user,
    )

    _REGISTERED = True
