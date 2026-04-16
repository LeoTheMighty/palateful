"""MCP server integration for Palateful.

Exposes the Palateful API as MCP tools so clients like Claude Desktop and
Claude Code can manage recipes, imports, shopping lists, and meal plans
through natural conversation.
"""

from mcp_server.server import build_mcp_app, call_endpoint, mcp

__all__ = ["mcp", "build_mcp_app", "call_endpoint"]
