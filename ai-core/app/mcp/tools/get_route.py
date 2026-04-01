import logging
import httpx
from app.config import ROUTING_SERVER_URL, ROUTING_API_KEY

logger = logging.getLogger(__name__)


DECLARATION = {
    "name": "get_route",
    "description": "Fetch a wheelchair-accessible route between two coordinates using the routing server.",
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


def execute(args: dict) -> dict:
    src_lat  = args["src_lat"]
    src_lon  = args["src_lon"]
    dest_lat = args["dest_lat"]
    dest_lon = args["dest_lon"]

    url = f"{ROUTING_SERVER_URL}/route/getSingleRoute"
    headers = {"Authorization": f"Bearer {ROUTING_API_KEY}"}
    params = {
        "srcLat":  src_lat,
        "srcLon":  src_lon,
        "destLat": dest_lat,
        "destLon": dest_lon,
    }

    try:
        with httpx.Client(timeout=30) as client:
            resp = client.get(url, headers=headers, params=params)
            resp.raise_for_status()
            data = resp.json()
    except httpx.TimeoutException:
        logger.error("Routing server timed out")
        return {"error": "Routing service timed out. Please try again."}
    except httpx.HTTPStatusError as exc:
        logger.error("Routing server error: %s", exc.response.status_code)
        return {"error": "Routing service returned an error. Please try again."}
    except Exception as exc:
        logger.error("Routing request failed: %s", exc)
        return {"error": "Could not reach the routing service."}

    steps = data.get("routes", {}).get("points", [])
    if not steps:
        return {"error": "No route found"}

    total_distance_ft = sum(s.get("distance", {}).get("value", 0) for s in steps)
    total_duration_s  = sum(s.get("duration", {}).get("value", 0) for s in steps)
    surfaces          = list({s.get("surface", "unknown") for s in steps if s.get("surface")})
    steep             = [s for s in steps if abs(s.get("incline", 0)) > 5]

    return {
        "total_distance_miles": round(total_distance_ft / 5280, 2),
        "estimated_minutes":    round(total_duration_s / 60, 1),
        "surfaces":             surfaces,
        "steep_segments_count": len(steep),
        "steps": [
            {
                "maneuver":  s.get("maneuver"),
                "distance":  s.get("distance", {}).get("text"),
                "duration":  s.get("duration", {}).get("text"),
                "surface":   s.get("surface"),
                "incline":   s.get("incline"),
            }
            for s in steps[:12]
        ],
    }
