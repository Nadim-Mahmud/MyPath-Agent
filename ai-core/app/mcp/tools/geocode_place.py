import logging
import asyncio

from app.geocoding_service import search_places

logger = logging.getLogger(__name__)


DECLARATION = {
    "name": "geocode_place",
    "description": "Resolve a place name into latitude/longitude coordinates with context bias.",
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "query": {"type": "STRING", "description": "Place name or address to search"},
            "limit": {"type": "NUMBER", "description": "Maximum number of matches (default 3)"},
            "bias_lat": {"type": "NUMBER", "description": "Latitude to bias search toward (optional)"},
            "bias_lon": {"type": "NUMBER", "description": "Longitude to bias search toward (optional)"},
        },
        "required": ["query"],
    },
}


def execute(args: dict) -> dict:
    query = str(args.get("query", "")).strip()
    if not query:
        return {"error": "Missing place query."}

    requested_limit = args.get("limit", 3)
    try:
        limit = max(1, min(int(requested_limit), 5))
    except (TypeError, ValueError):
        limit = 3

    bias_lat = None
    bias_lon = None
    try:
        if "bias_lat" in args:
            bias_lat = float(args["bias_lat"])
        if "bias_lon" in args:
            bias_lon = float(args["bias_lon"])
    except (TypeError, ValueError):
        pass

    try:
        results = asyncio.run(
            search_places(query=query, bias_lat=bias_lat, bias_lon=bias_lon, limit=limit)
        )
    except Exception as exc:
        logger.error("Geocoding request failed: %s", exc)
        return {"error": "Could not resolve that place right now."}

    if not results:
        return {"error": f"No location found for '{query}'."}

    return {
        "query": query,
        "results": results,
    }