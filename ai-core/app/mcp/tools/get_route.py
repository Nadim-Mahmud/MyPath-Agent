"""MCP tool: fetch a wheelchair-accessible route from the routing server."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import httpx

from app.constants import ROUTING_TIMEOUT_S, TOOL_GET_ROUTE
from app.mcp.base_tool import BaseTool

if TYPE_CHECKING:
    from app.config import Settings

logger = logging.getLogger(__name__)

_ROUTE_ENDPOINT: str = "/route/getSingleRoute"
_STEEP_INCLINE_THRESHOLD: float = 5.0
_FEET_PER_MILE: int = 5280
_SECONDS_PER_MINUTE: int = 60
_MAX_STEPS_IN_RESULT: int = 12


class GetRoute(BaseTool):
    """Fetch a wheelchair-accessible route between two coordinates."""

    def __init__(self, settings: "Settings") -> None:
        self._settings = settings

    @property
    def name(self) -> str:
        return TOOL_GET_ROUTE

    @property
    def declaration(self) -> dict:
        return {
            "name": self.name,
            "description": (
                "Fetch a wheelchair-accessible route between two coordinates "
                "using the routing server."
            ),
            "parameters": {
                "type": "OBJECT",
                "properties": {
                    "src_lat":  {"type": "NUMBER", "description": "Origin latitude"},
                    "src_lon":  {"type": "NUMBER", "description": "Origin longitude"},
                    "dest_lat": {"type": "NUMBER", "description": "Destination latitude"},
                    "dest_lon": {"type": "NUMBER", "description": "Destination longitude"},
                },
                "required": ["src_lat", "src_lon", "dest_lat", "dest_lon"],
            },
        }

    def execute(self, args: dict) -> dict:
        src_lat = args["src_lat"]
        src_lon = args["src_lon"]
        dest_lat = args["dest_lat"]
        dest_lon = args["dest_lon"]

        url = f"{self._settings.routing_server_url}{_ROUTE_ENDPOINT}"
        headers = {"Authorization": f"Bearer {self._settings.routing_api_key}"}
        params = {
            "srcLat": src_lat,
            "srcLon": src_lon,
            "destLat": dest_lat,
            "destLon": dest_lon,
        }

        try:
            with httpx.Client(timeout=ROUTING_TIMEOUT_S) as client:
                resp = client.get(url, headers=headers, params=params)
                resp.raise_for_status()
                data = resp.json()
        except httpx.TimeoutException:
            logger.error("Routing server timed out")
            return {"error": "Routing service timed out. Please try again."}
        except httpx.HTTPStatusError as exc:
            logger.error("Routing server HTTP error: status=%d", exc.response.status_code)
            return {"error": "Routing service returned an error. Please try again."}
        except Exception as exc:
            logger.error("Routing request failed: %s", exc)
            return {"error": "Could not reach the routing service."}

        steps = data.get("routes", {}).get("points", [])
        if not steps:
            return {"error": "No route found"}

        total_distance_ft = sum(s.get("distance", {}).get("value", 0) for s in steps)
        total_duration_s = sum(s.get("duration", {}).get("value", 0) for s in steps)
        surfaces = list({s.get("surface", "unknown") for s in steps if s.get("surface")})
        steep_count = sum(
            1 for s in steps if abs(s.get("incline", 0)) > _STEEP_INCLINE_THRESHOLD
        )

        return {
            "total_distance_miles": round(total_distance_ft / _FEET_PER_MILE, 2),
            "estimated_minutes": round(total_duration_s / _SECONDS_PER_MINUTE, 1),
            "surfaces": surfaces,
            "steep_segments_count": steep_count,
            "steps": [
                {
                    "maneuver": s.get("maneuver"),
                    "distance": s.get("distance", {}).get("text"),
                    "duration": s.get("duration", {}).get("text"),
                    "surface": s.get("surface"),
                    "incline": s.get("incline"),
                }
                for s in steps[:_MAX_STEPS_IN_RESULT]
            ],
        }
