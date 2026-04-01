import asyncio
import logging
import httpx

from app.geocoding_service import search_place_with_osm_meta

logger = logging.getLogger(__name__)

_OVERPASS_URL = "https://overpass-api.de/api/interpreter"
_HEADERS = {"User-Agent": "Wheelway/1.0 (wheelchair-navigation-ai)"}

DECLARATION = {
    "name": "get_place_accessibility",
    "description": (
        "Look up wheelchair accessibility information for a named building or place "
        "using OpenStreetMap data. Returns entrance accessibility, wheelchair tag, "
        "ramp availability, door type, and any accessibility descriptions mapped in OSM."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "place_name": {
                "type": "STRING",
                "description": "Name of the building or place, optionally with address (e.g. 'Benton Hall, Miami University, Oxford, Ohio')",
            },
            "bias_lat": {
                "type": "NUMBER",
                "description": "Latitude hint to prioritise nearby results (optional)",
            },
            "bias_lon": {
                "type": "NUMBER",
                "description": "Longitude hint to prioritise nearby results (optional)",
            },
        },
        "required": ["place_name"],
    },
}


def _wheelchair_label(value: str | None) -> str:
    return {
        "yes": "fully wheelchair accessible",
        "no": "not wheelchair accessible",
        "limited": "limited wheelchair accessibility",
    }.get(value or "", f"unknown ({value})" if value else "not specified in OSM")


def _parse_place_tags(tags: dict) -> dict:
    result: dict = {}
    if tags.get("wheelchair"):
        result["wheelchair"] = _wheelchair_label(tags["wheelchair"])
    if tags.get("wheelchair:description"):
        result["wheelchair_description"] = tags["wheelchair:description"]
    if tags.get("ramp") == "yes" or tags.get("ramp:wheelchair") == "yes":
        result["ramp"] = True
    if tags.get("step_count"):
        result["step_count"] = tags["step_count"]
    if tags.get("kerb"):
        result["kerb"] = tags["kerb"]
    for key in ("level", "building:levels", "amenity", "building", "name"):
        if tags.get(key):
            result[key] = tags[key]
    return result


def _parse_entrance(tags: dict) -> dict | None:
    entrance_type = tags.get("entrance")
    if not entrance_type:
        return None
    info: dict = {"entrance": entrance_type}
    if tags.get("wheelchair"):
        info["wheelchair"] = _wheelchair_label(tags["wheelchair"])
    if tags.get("door"):
        info["door"] = tags["door"]
    if tags.get("ramp") == "yes" or tags.get("ramp:wheelchair") == "yes":
        info["ramp"] = True
    if tags.get("step_count"):
        info["step_count"] = int(tags["step_count"])
    if tags.get("kerb"):
        info["kerb"] = tags["kerb"]
    if tags.get("name") or tags.get("ref"):
        info["label"] = tags.get("name") or tags.get("ref")
    return info


def _fetch_element_tags(osm_type: str, osm_id: int) -> dict:
    """Fetch full OSM tags for a specific element via Overpass."""
    t = {"node": "node", "way": "way", "relation": "relation"}.get(osm_type, "way")
    query = f"[out:json][timeout:15];{t}({osm_id});out tags;"
    try:
        with httpx.Client(timeout=20) as client:
            resp = client.post(_OVERPASS_URL, data={"data": query}, headers=_HEADERS)
            resp.raise_for_status()
            elements = resp.json().get("elements", [])
            if elements:
                return elements[0].get("tags", {})
    except Exception as exc:
        logger.warning("Overpass element fetch failed: %s", exc)
    return {}


def _fetch_entrances(lat: float, lon: float, radius: int = 80) -> list[dict]:
    """Query entrance nodes near a coordinate via Overpass."""
    query = f"[out:json][timeout:15];node[\"entrance\"](around:{radius},{lat},{lon});out tags;"
    try:
        with httpx.Client(timeout=20) as client:
            resp = client.post(_OVERPASS_URL, data={"data": query}, headers=_HEADERS)
            resp.raise_for_status()
            return [
                parsed
                for el in resp.json().get("elements", [])
                if (parsed := _parse_entrance(el.get("tags", {}))) is not None
            ]
    except Exception as exc:
        logger.warning("Overpass entrance query failed: %s", exc)
    return []


def execute(args: dict) -> dict:
    place_name: str = args.get("place_name", "").strip()
    bias_lat: float | None = args.get("bias_lat")
    bias_lon: float | None = args.get("bias_lon")

    if not place_name:
        return {"error": "place_name is required"}

    # Resolve place using the shared geocoding service (handles fallbacks + scoring)
    try:
        place = asyncio.run(
            search_place_with_osm_meta(place_name, bias_lat=bias_lat, bias_lon=bias_lon)
        )
    except Exception as exc:
        logger.error("Geocoding failed for place accessibility lookup: %s", exc)
        return {"error": "Could not resolve that place name. Try a more specific name."}

    if not place:
        return {
            "found": False,
            "message": f"No OSM record found for '{place_name}'. The building may not be mapped yet.",
        }

    lat = place["lat"]
    lon = place["lng"]
    osm_type = place["osm_type"]
    osm_id = place["osm_id"]
    extratags = place["extratags"]

    # Fetch full tags from Overpass (more complete than Nominatim extratags)
    element_tags = _fetch_element_tags(osm_type, osm_id)
    merged_tags = {**extratags, **element_tags}
    place_info = _parse_place_tags(merged_tags)

    entrances = _fetch_entrances(lat, lon)

    result: dict = {
        "found": True,
        "place": place["label"],
        "lat": lat,
        "lon": lon,
    }

    result["place_tags"] = place_info
    if not place_info:
        result["note"] = "This place is mapped in OSM but has no wheelchair accessibility tags recorded yet."

    result["entrances"] = entrances
    if not entrances and "note" not in result:
        result["note"] = "No entrance nodes with accessibility tags found within 80 m."

    return result
