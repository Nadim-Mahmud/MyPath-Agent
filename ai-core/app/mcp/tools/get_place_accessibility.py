"""MCP tool: look up wheelchair accessibility data for a named place via OSM."""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

import httpx

from app.constants import (
    OVERPASS_BASE_URL,
    NOMINATIM_USER_AGENT,
    OVERPASS_ENTRANCE_RADIUS_M,
    OVERPASS_MEMBER_QUERY_TIMEOUT_S,
    OVERPASS_RADIUS_QUERY_TIMEOUT_S,
    OVERPASS_TIMEOUT_S,
    TOOL_GET_PLACE_ACCESSIBILITY,
    WHEELCHAIR_LABEL_YES,
    WHEELCHAIR_LABEL_NO,
    WHEELCHAIR_LABEL_LIMITED,
    WHEELCHAIR_LABEL_NOT_SPECIFIED,
)
from app.mcp.base_tool import BaseTool

if TYPE_CHECKING:
    from app.services.geocoding_service import GeocodingService

logger = logging.getLogger(__name__)

_OVERPASS_HEADERS: dict[str, str] = {"User-Agent": NOMINATIM_USER_AGENT}
_NOTE_NO_TAGS: str = (
    "This place is mapped in OSM but has no wheelchair accessibility tags recorded yet."
)
_NOTE_NO_ENTRANCES: str = (
    f"No entrance nodes with accessibility tags found within {OVERPASS_ENTRANCE_RADIUS_M} m."
)


class GetPlaceAccessibility(BaseTool):
    """Look up wheelchair accessibility information for a named building or place."""

    def __init__(self, geocoding_service: "GeocodingService") -> None:
        self._geocoding = geocoding_service

    @property
    def name(self) -> str:
        return TOOL_GET_PLACE_ACCESSIBILITY

    @property
    def declaration(self) -> dict:
        return {
            "name": self.name,
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
                        "description": (
                            "Name of the building or place, optionally with address "
                            "(e.g. 'Benton Hall, Miami University, Oxford, Ohio')"
                        ),
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

    def execute(self, args: dict) -> dict:
        place_name: str = args.get("place_name", "").strip()
        bias_lat: float | None = args.get("bias_lat")
        bias_lon: float | None = args.get("bias_lon")

        if not place_name:
            return {"error": "place_name is required"}

        try:
            place = asyncio.run(
                self._geocoding.search_place_with_osm_meta(
                    place_name,
                    bias_lat=bias_lat,
                    bias_lon=bias_lon,
                )
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

        element_tags, entrances, ramps = self._fetch_all(osm_type, osm_id, lat, lon)

        merged_tags = {**extratags, **element_tags}
        place_info = self._parse_place_tags(merged_tags)

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
            result["note"] = _NOTE_NO_TAGS
        elif not entrances:
            result["note"] = _NOTE_NO_ENTRANCES

        return result

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _fetch_all(
        self,
        osm_type: str,
        osm_id: int,
        lat: float,
        lon: float,
    ) -> tuple[dict, list[dict], list[dict]]:
        """Fetch building tags + entrance nodes + ramp nodes in at most 2 Overpass requests.

        Request 1 (member query): fetches the element AND all its member nodes
        in a single round-trip.  Covers entrances/ramps mapped as building members.

        Request 2 (radius fallback, only when request 1 found no entrances/ramps):
        queries entrances and ramps by radius in one union query.
        """
        t = {"node": "node", "way": "way", "relation": "relation"}.get(osm_type, "way")
        cached_building_tags: dict = {}

        if t in ("way", "relation"):
            member_ref = "w" if t == "way" else "r"
            member_query = (
                f"[out:json][timeout:{OVERPASS_MEMBER_QUERY_TIMEOUT_S}];"
                f"{t}({osm_id})->.b;"
                f"(.b; node({member_ref}.b););"
                f"out body;"
            )
            try:
                elements = self._overpass_request(member_query)
                building_tags, entrances, ramps = self._classify_nodes(elements)
                logger.info(
                    "Member query: osm_id=%d building_tags=%d entrances=%d ramps=%d",
                    osm_id,
                    len(building_tags),
                    len(entrances),
                    len(ramps),
                )
                if entrances or ramps:
                    return building_tags, entrances, ramps
                cached_building_tags = building_tags
            except Exception as exc:
                logger.warning("Overpass member query failed: %s", exc)

        radius_query = (
            f"[out:json][timeout:{OVERPASS_RADIUS_QUERY_TIMEOUT_S}];"
            f"("
            f'  node["entrance"](around:{OVERPASS_ENTRANCE_RADIUS_M},{lat},{lon});'
            f'  node[~"^ramp(:wheelchair)?$"~"yes"](around:{OVERPASS_ENTRANCE_RADIUS_M},{lat},{lon});'
            f");"
            f"out body;"
        )
        try:
            elements = self._overpass_request(radius_query)
            _, entrances, ramps = self._classify_nodes(elements)
            logger.info(
                "Radius fallback: osm_id=%d entrances=%d ramps=%d",
                osm_id,
                len(entrances),
                len(ramps),
            )
            return cached_building_tags, entrances, ramps
        except Exception as exc:
            logger.warning("Overpass radius fallback failed: %s", exc)

        return cached_building_tags, [], []

    @staticmethod
    def _overpass_request(query: str) -> list[dict]:
        with httpx.Client(timeout=OVERPASS_TIMEOUT_S) as client:
            resp = client.post(OVERPASS_BASE_URL, data={"data": query}, headers=_OVERPASS_HEADERS)
            resp.raise_for_status()
            return resp.json().get("elements", [])

    @staticmethod
    def _classify_nodes(
        elements: list[dict],
    ) -> tuple[dict, list[dict], list[dict]]:
        """Partition an Overpass elements list into building tags, entrances, and ramps."""
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
                parsed = GetPlaceAccessibility._parse_entrance(tags)
                if parsed is not None:
                    parsed["lat"] = el["lat"]
                    parsed["lon"] = el["lon"]
                    entrances.append(parsed)
            elif GetPlaceAccessibility._is_ramp_node(tags):
                ramps.append({"lat": el["lat"], "lon": el["lon"], "tags": tags})

        return building_tags, entrances, ramps

    @staticmethod
    def _wheelchair_label(value: str | None) -> str:
        return {
            "yes": WHEELCHAIR_LABEL_YES,
            "no": WHEELCHAIR_LABEL_NO,
            "limited": WHEELCHAIR_LABEL_LIMITED,
        }.get(value or "", f"unknown ({value})" if value else WHEELCHAIR_LABEL_NOT_SPECIFIED)

    @staticmethod
    def _parse_place_tags(tags: dict) -> dict:
        result: dict = {}
        if tags.get("wheelchair"):
            result["wheelchair"] = GetPlaceAccessibility._wheelchair_label(tags["wheelchair"])
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

    @staticmethod
    def _parse_entrance(tags: dict) -> dict | None:
        entrance_type = tags.get("entrance")
        if not entrance_type:
            return None
        info: dict = {"entrance": entrance_type}
        if tags.get("wheelchair"):
            info["wheelchair"] = GetPlaceAccessibility._wheelchair_label(tags["wheelchair"])
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

    @staticmethod
    def _is_ramp_node(tags: dict) -> bool:
        return tags.get("ramp") == "yes" or tags.get("ramp:wheelchair") == "yes"
