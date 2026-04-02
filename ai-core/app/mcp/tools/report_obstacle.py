"""MCP tool: report an accessibility obstacle at a location (stub)."""

from __future__ import annotations

from app.constants import TOOL_REPORT_OBSTACLE
from app.mcp.base_tool import BaseTool

_STUB_MESSAGE: str = "Obstacle report recorded. Thank you for improving accessibility data."


class ReportObstacle(BaseTool):
    """Report an accessibility barrier at a location.

    This is a stub implementation; obstacle storage has not been built yet.
    """

    @property
    def name(self) -> str:
        return TOOL_REPORT_OBSTACLE

    @property
    def declaration(self) -> dict:
        return {
            "name": self.name,
            "description": (
                "Report an accessibility barrier (e.g. broken ramp, missing curb cut) "
                "at a location."
            ),
            "parameters": {
                "type": "OBJECT",
                "properties": {
                    "lat":         {"type": "NUMBER", "description": "Latitude of the obstacle"},
                    "lon":         {"type": "NUMBER", "description": "Longitude of the obstacle"},
                    "description": {"type": "STRING", "description": "Description of the barrier"},
                    "type": {
                        "type": "STRING",
                        "description": "Type: broken_ramp, missing_curb_cut, construction, other",
                    },
                },
                "required": ["lat", "lon", "description"],
            },
        }

    def execute(self, args: dict) -> dict:
        return {
            "status": "received",
            "message": _STUB_MESSAGE,
            "lat": args.get("lat"),
            "lon": args.get("lon"),
        }
