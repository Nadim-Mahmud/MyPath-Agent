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


def _is_ramp_node(tags: dict) -> bool:
    return tags.get("ramp") == "yes" or tags.get("ramp:wheelchair") == "yes"


def _classify_nodes(elements: list[dict]) -> tuple[dict, list[dict], list[dict]]:
    """
    From a flat Overpass elements list, return:
      (building_tags, entrance_nodes, ramp_nodes)
    Building element is the first non-node or the way/relation; nodes are filtered by tags.
    """
    building_tags: dict = {}
    entrances: list[dict] = []
    ramps: list[dict] = []

    for el in elements:
        el_type = el.get("type")
        tags = el.get("tags", {})

        if el_type in ("way", "relation"):
            building_tags = tags
            continue

        if el_type != "node" or el.get("lat") is None:
            continue

        if tags.get("entrance"):
            parsed = _parse_entrance(tags)
            if parsed is not None:
                parsed["lat"] = el["lat"]
                parsed["lon"] = el["lon"]
                entrances.append(parsed)
        elif _is_ramp_node(tags):
            ramps.append({"lat": el["lat"], "lon": el["lon"], "tags": tags})

    return building_tags, entrances, ramps


def _overpass_request(query: str) -> list[dict]:
    """Execute a single Overpass query and return elements list."""
    with httpx.Client(timeout=25) as client:
        resp = client.post(_OVERPASS_URL, data={"data": query}, headers=_HEADERS)
        resp.raise_for_status()
        return resp.json().get("elements", [])


def _fetch_all(osm_type: str, osm_id: int, lat: float, lon: float) -> tuple[dict, list[dict], list[dict]]:
    """
    Fetch building tags + entrance nodes + ramp nodes in at most 2 Overpass requests.

    Request 1 (member query): fetches the element itself AND all its member nodes
    in a single round-trip. Covers entrances and ramps that are mapped as building members.

    Request 2 (radius fallback, only if request 1 found no entrances/ramps):
    queries entrances AND ramps by radius in one union query.
    """
    t = {"node": "node", "way": "way", "relation": "relation"}.get(osm_type, "way")

    # --- Request 1: element + all member nodes in one shot ---
    if t in ("way", "relation"):
        member_ref = "w" if t == "way" else "r"
        query = (
            f"[out:json][timeout:20];"
            f"{t}({osm_id})->.b;"
            f"(.b; node({member_ref}.b););"
            f"out body;"
        )
        try:
            elements = _overpass_request(query)
            building_tags, entrances, ramps = _classify_nodes(elements)
            logger.info(
                "Member query: osm_id=%d building_tags=%d entrances=%d ramps=%d",
                osm_id, len(building_tags), len(entrances), len(ramps),
            )
            # If we got building tags and either entrances or ramps, we're done
            if entrances or ramps:
                return building_tags, entrances, ramps
            # If no member entrances/ramps, fall through to radius — but keep building_tags
            cached_building_tags = building_tags
        except Exception as exc:
            logger.warning("Overpass member query failed (429 or other): %s", exc)
            cached_building_tags = {}
    else:
        cached_building_tags = {}

    # --- Request 2: single radius union query for entrances + ramps ---
    radius = 60
    query = (
        f"[out:json][timeout:15];"
        f"("
        f"  node[\"entrance\"](around:{radius},{lat},{lon});"
        f"  node[~\"^ramp(:wheelchair)?$\"~\"yes\"](around:{radius},{lat},{lon});"
        f");"
        f"out body;"
    )
    try:
        elements = _overpass_request(query)
        # Radius query returns only nodes, no building element — inject a dummy so _classify_nodes works
        _, entrances, ramps = _classify_nodes(elements)
        logger.info(
            "Radius fallback: osm_id=%d entrances=%d ramps=%d",
            osm_id, len(entrances), len(ramps),
        )
        return cached_building_tags, entrances, ramps
    except Exception as exc:
        logger.warning("Overpass radius fallback failed: %s", exc)

    return cached_building_tags, [], []


def execute(args: dict) -> dict:
    place_name: str = args.get("place_name", "").strip()
    bias_lat: float | None = args.get("bias_lat")
    bias_lon: float | None = args.get("bias_lon")

    if not place_name:
        return {"error": "place_name is required"}

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

    # Single call: at most 2 Overpass requests total
    element_tags, entrances, ramps = _fetch_all(osm_type, osm_id, lat, lon)

    # Nominatim extratags are a cheap fallback for building-level tags (no extra request)
    merged_tags = {**extratags, **element_tags}
    place_info = _parse_place_tags(merged_tags)

    result: dict = {
        "found": True,
        "place": place["label"],
        "lat": lat,
        "lon": lon,
        "place_tags": place_info,
        "entrances": entrances,
        "ramps": ramps,
    }

    if not place_info:
        result["note"] = "This place is mapped in OSM but has no wheelchair accessibility tags recorded yet."
    elif not entrances:
        result["note"] = "No entrance nodes with accessibility tags found within 60 m."

    return result
