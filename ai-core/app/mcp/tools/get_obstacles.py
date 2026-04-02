"""MCP tool: retrieve known accessibility obstacles near a location (stub)."""

from __future__ import annotations

from app.constants import TOOL_GET_OBSTACLES
from app.mcp.base_tool import BaseTool

_STUB_MESSAGE: str = (
    "Obstacle database not yet populated. No known obstacles in this area."
)


class GetObstacles(BaseTool):
    """Retrieve known accessibility obstacles near a given location.

    This is a stub implementation; obstacle storage has not been built yet.
    """

    @property
    def name(self) -> str:
        return TOOL_GET_OBSTACLES

    @property
    def declaration(self) -> dict:
        return {
            "name": self.name,
            "description": "Retrieve known accessibility obstacles near a given location.",
            "parameters": {
                "type": "OBJECT",
                "properties": {
                    "lat":    {"type": "NUMBER", "description": "Latitude to search near"},
                    "lon":    {"type": "NUMBER", "description": "Longitude to search near"},
                    "radius": {"type": "NUMBER", "description": "Search radius in metres (default 500)"},
                },
                "required": ["lat", "lon"],
            },
        }

    def execute(self, args: dict) -> dict:  # noqa: ARG002
        return {"obstacles": [], "message": _STUB_MESSAGE}
