"""MCP tool registry and dispatcher.

:class:`MCPServer` owns the set of registered tools, exposes their declarations
to the LLM provider, and dispatches ``execute_tool`` calls to the correct
implementation.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from app.mcp.base_tool import BaseTool

if TYPE_CHECKING:
    from app.services.geocoding_service import GeocodingService
    from app.config import Settings

logger = logging.getLogger(__name__)


class MCPServer:
    """Registry for MCP tools.  Provides declarations and dispatches execution."""

    def __init__(self, settings: "Settings", geocoding_service: "GeocodingService") -> None:
        self._tools: dict[str, BaseTool] = {}
        self._register_default_tools(settings, geocoding_service)

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def register(self, tool: BaseTool) -> None:
        """Register a tool instance.  Raises :class:`ValueError` on name collision."""
        if tool.name in self._tools:
            raise ValueError(f"Tool '{tool.name}' is already registered.")
        self._tools[tool.name] = tool
        logger.debug("Registered MCP tool: %s", tool.name)

    def execute_tool(self, name: str, args: dict) -> dict:
        """Dispatch a tool call by name.  Returns an error dict for unknown tools."""
        tool = self._tools.get(name)
        if tool is None:
            logger.warning("Unknown tool requested: %s", name)
            return {"error": f"Unknown tool: {name}"}
        return tool.execute(args)

    @property
    def tool_declarations(self) -> list[dict]:
        """Return all registered tool declarations for passing to the LLM."""
        return [t.declaration for t in self._tools.values()]

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _register_default_tools(
        self,
        settings: "Settings",
        geocoding_service: "GeocodingService",
    ) -> None:
        # Import here to avoid circular imports at module load time
        from app.mcp.tools.get_route import GetRoute
        from app.mcp.tools.geocode_place import GeocodePlace
        from app.mcp.tools.get_place_accessibility import GetPlaceAccessibility
        from app.mcp.tools.get_obstacles import GetObstacles
        from app.mcp.tools.report_obstacle import ReportObstacle

        for tool in (
            GetRoute(settings=settings),
            GeocodePlace(geocoding_service=geocoding_service),
            GetPlaceAccessibility(geocoding_service=geocoding_service),
            GetObstacles(),
            ReportObstacle(),
        ):
            self.register(tool)
