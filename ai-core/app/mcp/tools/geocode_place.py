"""MCP tool: resolve a place name into coordinates via Nominatim geocoding."""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

from app.constants import TOOL_GEOCODE_PLACE
from app.mcp.base_tool import BaseTool

if TYPE_CHECKING:
    from app.services.geocoding_service import GeocodingService

logger = logging.getLogger(__name__)

_DEFAULT_LIMIT: int = 3
_MIN_LIMIT: int = 1
_MAX_LIMIT: int = 5


class GeocodePlace(BaseTool):
    """Resolve a place name or address into latitude/longitude coordinates."""

    def __init__(self, geocoding_service: "GeocodingService") -> None:
        self._geocoding = geocoding_service

    @property
    def name(self) -> str:
        return TOOL_GEOCODE_PLACE

    @property
    def declaration(self) -> dict:
        return {
            "name": self.name,
            "description": "Resolve a place name into latitude/longitude coordinates with context bias.",
            "parameters": {
                "type": "OBJECT",
                "properties": {
                    "query":    {"type": "STRING", "description": "Place name or address to search"},
                    "limit":    {"type": "NUMBER", "description": "Maximum number of matches (default 3)"},
                    "bias_lat": {"type": "NUMBER", "description": "Latitude to bias search toward (optional)"},
                    "bias_lon": {"type": "NUMBER", "description": "Longitude to bias search toward (optional)"},
                },
                "required": ["query"],
            },
        }

    def execute(self, args: dict) -> dict:
        query = str(args.get("query", "")).strip()
        if not query:
            return {"error": "Missing place query."}

        try:
            limit = max(_MIN_LIMIT, min(int(args.get("limit", _DEFAULT_LIMIT)), _MAX_LIMIT))
        except (TypeError, ValueError):
            limit = _DEFAULT_LIMIT

        bias_lat: float | None = None
        bias_lon: float | None = None
        try:
            if "bias_lat" in args:
                bias_lat = float(args["bias_lat"])
            if "bias_lon" in args:
                bias_lon = float(args["bias_lon"])
        except (TypeError, ValueError):
            pass

        try:
            results = asyncio.run(
                self._geocoding.search_places(
                    query=query,
                    bias_lat=bias_lat,
                    bias_lon=bias_lon,
                    limit=limit,
                )
            )
        except Exception as exc:
            logger.error("Geocoding request failed: %s", exc)
            return {"error": "Could not resolve that place right now."}

        if not results:
            return {"error": f"No location found for '{query}'."}

        return {"query": query, "results": results}
