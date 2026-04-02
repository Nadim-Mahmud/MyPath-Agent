import logging
import re
import asyncio
import httpx
import json

from app.models import ChatRequest, ChatResponse, ChatContext
from app import session_store
from app import gemini_service
from app.mcp.mcp_server import execute_tool

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

_MAX_CONTEXT_ROUTE_SEGMENTS = 40
_MAX_FOCUSED_HISTORY_MESSAGES = 6
_INTENT_ROUTE = "route"
_INTENT_ACCESSIBILITY = "accessibility"
_INTENT_GENERAL = "general"

_ROUTE_INTENT_PATTERNS = [
    re.compile(r"\b(route|directions|navigate|navigation|take me to|way to)\b", re.IGNORECASE),
    re.compile(r"\bfrom\b.+\bto\b", re.IGNORECASE),
    re.compile(r"\bhow\s+do\s+i\s+get\s+to\b", re.IGNORECASE),
]

_ACCESSIBILITY_INTENT_PATTERNS = [
    re.compile(r"\b(accessible|accessibility|wheelchair)\b", re.IGNORECASE),
    re.compile(r"\b(ramp|entrance|door|elevator|lift|curb|kerb|step)\b", re.IGNORECASE),
    re.compile(r"\bis\b.+\baccessible\b", re.IGNORECASE),
]


def _detect_user_intent(message: str) -> str:
    text = (message or "").strip()
    if not text:
        return _INTENT_GENERAL

    has_route = any(p.search(text) for p in _ROUTE_INTENT_PATTERNS)
    has_accessibility = any(p.search(text) for p in _ACCESSIBILITY_INTENT_PATTERNS)

    if has_route and not has_accessibility:
        return _INTENT_ROUTE
    if has_accessibility and not has_route:
        return _INTENT_ACCESSIBILITY
    if has_route and has_accessibility:
        # Explicit routing asks should prefer route behavior.
        if re.search(r"\b(from\b.+\bto\b|route|directions|navigate)\b", text, re.IGNORECASE):
            return _INTENT_ROUTE
        return _INTENT_ACCESSIBILITY
    return _INTENT_GENERAL


def _route_destination_fields(route_action: object | None) -> tuple[float | None, float | None, str | None]:
    """Extract destination fields from either dict-based or model-based route actions."""
    if route_action is None:
        return None, None, None

    destination: object | None
    if isinstance(route_action, dict):
        destination = route_action.get("destination")
        if isinstance(destination, dict):
            return destination.get("lat"), destination.get("lng"), destination.get("label")
        return None, None, None

    destination = getattr(route_action, "destination", None)
    if destination is None:
        return None, None, None

    return (
        getattr(destination, "lat", None),
        getattr(destination, "lng", None),
        getattr(destination, "label", None),
    )


async def _reverse_geocode_label(lat: float, lng: float) -> str:
    """Resolve coordinates to a readable address label."""
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                f"https://nominatim.openstreetmap.org/reverse?lat={lat}&lon={lng}&format=json",
                headers={"User-Agent": "Wheelway/1.0 (wheelchair-navigation)"},
            )
            if resp.status_code == 200:
                data = resp.json()
                if isinstance(data.get("display_name"), str) and data["display_name"].strip():
                    return data["display_name"].strip()
    except Exception as exc:
        logger.debug("Reverse geocode failed: %s", exc)
    
    return f"{lat:.5f}, {lng:.5f}"


def _compact_active_route(active_route: object) -> dict | None:
    if not isinstance(active_route, dict):
        return None

    routes = active_route.get("routes")
    if not isinstance(routes, dict):
        return None

    points = routes.get("points")
    if not isinstance(points, list) or not points:
        return None

    compact_segments = []
    surface_counts: dict[str, int] = {}
    total_distance_ft = 0.0
    total_duration_s = 0.0
    steep_segments = 0

    for idx, seg in enumerate(points[:_MAX_CONTEXT_ROUTE_SEGMENTS]):
        if not isinstance(seg, dict):
            continue

        surface = str(seg.get("surface") or "unknown")
        distance = seg.get("distance") if isinstance(seg.get("distance"), dict) else {}
        duration = seg.get("duration") if isinstance(seg.get("duration"), dict) else {}

        try:
            incline = float(seg.get("incline", 0) or 0)
        except (TypeError, ValueError):
            incline = 0.0

        try:
            distance_value = float(distance.get("value", 0) or 0)
        except (TypeError, ValueError):
            distance_value = 0.0

        try:
            duration_value = float(duration.get("value", 0) or 0)
        except (TypeError, ValueError):
            duration_value = 0.0

        compact_segments.append(
            {
                "index": idx,
                "surface": surface,
                "distance": {
                    "value": distance_value,
                    "type": distance.get("type"),
                    "text": distance.get("text"),
                },
                "duration": {
                    "value": duration_value,
                    "type": duration.get("type"),
                    "text": duration.get("text"),
                },
                "maneuver": seg.get("maneuver"),
                "incline": incline,
            }
        )

        surface_counts[surface] = surface_counts.get(surface, 0) + 1
        total_distance_ft += distance_value
        total_duration_s += duration_value
        if abs(incline) > 5:
            steep_segments += 1

    return {
        "segments_total": len(points),
        "segments_in_context": len(compact_segments),
        "truncated": len(points) > _MAX_CONTEXT_ROUTE_SEGMENTS,
        "summary": {
            "surface_counts": surface_counts,
            "steep_segments_count": steep_segments,
            "total_distance_ft": round(total_distance_ft, 2),
            "total_duration_s": round(total_duration_s, 2),
        },
        "segments": compact_segments,
    }


_CURRENT_LOCATION_PATTERNS = [
    re.compile(r"(?:from\s+)?(?:my|current)\s+location\s+to\s+(.+)", re.IGNORECASE),
    re.compile(r"(?:navigate|route|directions)\s+(?:me\s+)?to\s+(.+)", re.IGNORECASE),
    re.compile(r"to\s+([A-Z][^.!?]+(?:[A-Z][^.!?]*)*)", re.IGNORECASE),
    re.compile(r"\bto\s+(.+)", re.IGNORECASE),
    # Match full addresses with numbers and street names
    re.compile(r"(?:to|route to|navigate to)?\s*(.+?(?:street|st|avenue|ave|road|rd|boulevard|blvd|drive|dr|building|building?).+)", re.IGNORECASE),
]


def _is_negative_geocoding_message(text: str) -> bool:
    """Check if a message is a failed geocoding or routing attempt."""
    lower = text.lower()
    failure_keywords = ["locate", "location", "find", "address", "place", "geocod", "route", "direct"]
    negative_phrases = ["unable", "sorry", "cannot", "can't", "failed", "unavailable", "regret", "couldn't", "trouble", "apologize", "having trouble"]

    has_failure_context = any(kw in lower for kw in failure_keywords)
    has_negative = any(phrase in lower for phrase in negative_phrases)

    return has_failure_context and has_negative


def _strip_negative_geocoding_history(history: list[dict]) -> list[dict]:
    """Remove the most recent negative geocoding message from history if present."""
    if not history:
        return history
    
    # Check if the last model message is a negative geocoding failure
    for i in range(len(history) - 1, -1, -1):
        entry = history[i]
        if entry.get("role") == "model":
            parts = entry.get("parts", [])
            if parts and isinstance(parts[0], dict):
                text = parts[0].get("text", "")
                if _is_negative_geocoding_message(text):
                    # Remove this message
                    logger.info("Stripping negative geocoding message from retry history")
                    return history[:i] + history[i+1:]
            break
    
    return history


def _enrich_message(message: str, context: ChatContext | None, user_intent: str) -> str:
    if context is None:
        if user_intent == _INTENT_ROUTE:
            return message + "\n\n[Intent] route request. Prioritize routing actions."
        if user_intent == _INTENT_ACCESSIBILITY:
            return message + "\n\n[Intent] accessibility information request. Provide accessibility details; do not create a route unless explicitly asked."
        return message
    lines = [
        message,
        "",
        "[Instruction] Prioritize this latest user request. Use earlier history only for short continuity.",
        f"[Intent] {user_intent}",
        (
            "[Intent handling] User is asking for route planning. Prioritize route computation."
            if user_intent == _INTENT_ROUTE
            else "[Intent handling] User is asking for accessibility information. Do not create a route unless explicitly requested."
            if user_intent == _INTENT_ACCESSIBILITY
            else "[Intent handling] Answer directly. Only route when explicitly requested."
        ),
        "",
        "[Context]",
    ]
    if context.user_location:
        lines.append(f"User GPS: {context.user_location.lat}, {context.user_location.lng}")
        lines.append("If user asks from current location, use this User GPS as route origin.")
    if context.map_center:
        lines.append(f"Map centre: {context.map_center.lat}, {context.map_center.lng}")
    if context.active_route is not None:
        compact_route = _compact_active_route(context.active_route)
        if compact_route is None:
            lines.append("User has no active route currently shown on the map.")
            lines.append("Ignore prior turns that imply a route is still active.")
        else:
            lines.append("User has active route.")
            lines.append("Active route accessibility summary (coordinates removed):")
            lines.append(json.dumps(compact_route, separators=(",", ":")))
    else:
        lines.append("User has no active route currently shown on the map.")
        lines.append("Ignore prior turns that imply a route is still active.")
    return "\n".join(lines)


def _strip_context_block(text: str) -> str:
    marker = "\n\n[Context]"
    if marker in text:
        return text.split(marker, 1)[0].strip()
    return text


def _build_focused_history(history: list[dict], strip_negative_geocoding: bool = False) -> list[dict]:
    # If this is a retry after a failed geocoding, remove that negative message
    if strip_negative_geocoding:
        history = _strip_negative_geocoding_history(history)
    
    focused = history[-_MAX_FOCUSED_HISTORY_MESSAGES:]
    sanitized: list[dict] = []

    for entry in focused:
        role = entry.get("role")
        parts = entry.get("parts")
        if role not in {"user", "model"} or not isinstance(parts, list):
            continue

        sanitized_parts = []
        for part in parts:
            if not isinstance(part, dict):
                continue
            text = part.get("text")
            if not isinstance(text, str):
                continue

            if role == "user":
                text = _strip_context_block(text)
            sanitized_parts.append({"text": text})

        if sanitized_parts:
            sanitized.append({"role": role, "parts": sanitized_parts})

    return sanitized


def _extract_destination_from_message(message: str) -> str | None:
    for pattern in _CURRENT_LOCATION_PATTERNS:
        match = pattern.search(message.strip())
        if not match:
            continue
        candidate = match.group(1).strip(" .,!?")
        if candidate:
            return candidate
    return None


def _try_current_location_route(req: ChatRequest) -> tuple[ChatResponse | None, str | None]:
    """
    Returns (ChatResponse, None)       — route found, use it directly.
            (None, pre_resolved_context) — place resolved but routing failed; context
                                           tells Gemini what we already know so it can
                                           skip geocoding/accessibility tool calls.
            (None, None)               — could not even resolve the place.
    """
    if req.context is None or req.context.user_location is None:
        return None, None

    destination_query = _extract_destination_from_message(req.message)
    if not destination_query:
        return None, None

    src = req.context.user_location
    has_street_markers = bool(re.search(
        r"\d+\s+(street|st|avenue|ave|road|rd|boulevard|blvd|drive|dr|building)",
        destination_query, re.IGNORECASE,
    ))

    # --- Resolve place + accessibility in ONE call for named buildings,
    #     or geocode only for explicit street addresses.
    building_lat: float | None = None
    building_lng: float | None = None
    destination_label: str = destination_query
    coords_to_try: list[tuple[float, float, str]] = []
    accessibility_summary: str = ""

    if not has_street_markers:
        # get_place_accessibility geocodes internally — saves a redundant Nominatim call
        accessibility = execute_tool(
            "get_place_accessibility",
            {
                "place_name": destination_query,
                "bias_lat": src.lat,
                "bias_lon": src.lng,
            },
        )
        if isinstance(accessibility, dict) and accessibility.get("found"):
            building_lat = float(accessibility["lat"])
            building_lng = float(accessibility["lon"])
            destination_label = str(accessibility.get("place") or destination_query)

            for entrance in accessibility.get("entrances", []):
                wheelchair = entrance.get("wheelchair", "")
                elat, elon = entrance.get("lat"), entrance.get("lon")
                if "fully" in wheelchair and elat is not None and elon is not None:
                    coords_to_try.append((float(elat), float(elon), destination_label + " (accessible entrance)"))

            # Build a summary to inject into Gemini if routing fails below
            entrance_coords = [(c[0], c[1]) for c in coords_to_try]
            accessibility_summary = (
                f'Destination "{destination_query}" already resolved to '
                f"lat={building_lat:.5f}, lng={building_lng:.5f}. "
                + (
                    f"Accessible entrances at: {entrance_coords}. "
                    if entrance_coords else "No accessible entrances found in OSM. "
                )
                + "do NOT call geocode_place or get_place_accessibility again. "
                "Call get_route directly using the coordinates above."
            )
    else:
        # Street address — plain geocode is sufficient, no accessibility lookup needed
        geocoded = execute_tool("geocode_place", {"query": destination_query, "limit": 10})
        if not (isinstance(geocoded, dict) and not geocoded.get("error")):
            return None, None
        results = geocoded.get("results") or []
        if results and isinstance(results[0], dict):
            first = results[0]
            building_lat = float(first.get("lat", 0))
            building_lng = float(first.get("lng", 0))
            destination_label = str(first.get("label") or destination_query)

    if building_lat is None or building_lng is None:
        return None, None

    # Centroid is always the last resort
    coords_to_try.append((building_lat, building_lng, destination_label))

    for dest_lat, dest_lng, label in coords_to_try:
        route_result = execute_tool(
            "get_route",
            {"src_lat": src.lat, "src_lon": src.lng, "dest_lat": dest_lat, "dest_lon": dest_lng},
        )
        if not (isinstance(route_result, dict) and route_result.get("error")):
            distance = route_result.get("total_distance_miles") if isinstance(route_result, dict) else None
            eta = route_result.get("estimated_minutes") if isinstance(route_result, dict) else None
            return ChatResponse(
                session_id=req.session_id,
                message=(
                    f"I found an accessible route from your current location to **{label}**. "
                    f"Estimated distance: **{distance} mi**, travel time: **{eta} min**. "
                    "I've loaded it on the map for you."
                ),
                route_action={
                    "origin": {"lat": src.lat, "lng": src.lng, "label": "My Location"},
                    "destination": {"lat": dest_lat, "lng": dest_lng, "label": label},
                },
            ), None

    # Place resolved but every routing attempt failed — hand off to Gemini with context
    return None, accessibility_summary or None


def chat(req: ChatRequest) -> ChatResponse:
    history = session_store.get_history(req.session_id)
    user_intent = _detect_user_intent(req.message)
    logger.info("Loaded session history: session_id=%s history_messages=%d", req.session_id, len(history))
    logger.info("Detected user intent: session_id=%s intent=%s", req.session_id, user_intent)
    
    # Detect if this is a retry: if previous model message is negative geocoding AND
    # current message asks for a route/place, strip that negative context
    is_retry_after_geocoding_failure = False
    if user_intent == _INTENT_ROUTE and len(history) >= 2:
        # Find the most recent model message
        for i in range(len(history) - 1, -1, -1):
            if history[i].get("role") == "model":
                parts = history[i].get("parts", [])
                if parts and isinstance(parts[0], dict):
                    model_text = parts[0].get("text", "")
                    if _is_negative_geocoding_message(model_text):
                        # Check if current message also mentions a location/place
                        if _extract_destination_from_message(req.message):
                            is_retry_after_geocoding_failure = True
                            logger.info("Detected retry after geocoding failure: session_id=%s", req.session_id)
                break
    
    focused_history = _build_focused_history(history, strip_negative_geocoding=is_retry_after_geocoding_failure)
    logger.info(
        "Prepared focused history: session_id=%s focused_messages=%d stripped_negative=%s",
        req.session_id,
        len(focused_history),
        is_retry_after_geocoding_failure,
    )

    fallback_response, pre_resolved_context = (
        _try_current_location_route(req) if user_intent == _INTENT_ROUTE else (None, None)
    )
    if fallback_response is not None:
        logger.info("Used current-location route fallback: session_id=%s", req.session_id)
        dest_lat, dest_lng, dest_label = _route_destination_fields(fallback_response.route_action)
        route_note = (
            f"[Route found] A wheelchair-accessible route was successfully generated to "
            f"{dest_label or 'the destination'} "
            f"(lat={dest_lat}, lng={dest_lng}). "
            "The route is loaded on the map. No need to call any routing tools again for this request."
        )
        session_store.add_message(req.session_id, "user", req.message)
        session_store.add_message(req.session_id, "model", route_note + " " + fallback_response.message)
        return fallback_response

    enriched = _enrich_message(req.message, req.context, user_intent)
    # If the fast path resolved the place but routing failed, inject what we already know
    # so Gemini skips geocoding/accessibility tool calls and goes straight to get_route.
    if pre_resolved_context:
        enriched = enriched + "\n\n[Pre-resolved] " + pre_resolved_context
    logger.info(
        "Prepared enriched user message: session_id=%s enriched_chars=%d",
        req.session_id,
        len(enriched),
    )

    completion = gemini_service.complete(enriched, focused_history)
    logger.info(
        "Received model response: session_id=%s reply_chars=%d has_route_action=%s",
        req.session_id,
        len(completion.message),
        completion.route_action is not None,
    )

    # If Gemini succeeded in computing a route (route_action present),
    # but the message is apologetic, override it with a positive message
    message = completion.message
    route_action = completion.route_action

    if user_intent == _INTENT_ACCESSIBILITY:
        route_action = None

    if route_action:
        # Check if message sounds apologetic/negative
        is_negative = any(
            phrase in message.lower()
            for phrase in [
                "unable",
                "sorry",
                "cannot",
                "can't",
                "unfortunately",
                "regret",
                "unavailable",
            ]
        )
        if is_negative:
            # Replace with positive message
            dest_lat, dest_lng, dest_label = _route_destination_fields(route_action)
            dest_label = (dest_label or "").strip()
            # If label is missing, try reverse geocoding
            if not dest_label:
                try:
                    if dest_lat is not None and dest_lng is not None:
                        dest_label = asyncio.run(_reverse_geocode_label(dest_lat, dest_lng))
                except Exception as exc:
                    logger.warning("Failed to reverse geocode destination: %s", exc)
                    dest_label = "your destination"
            
            if not dest_label:
                dest_label = "your destination"

            message = (
                f"I found an accessible route to **{dest_label}**. "
                "I've loaded it on the map for you. Check it out!"
            )
            logger.info(
                "Overrode negative message with route success: session_id=%s",
                req.session_id,
            )

    session_store.add_message(req.session_id, "user", enriched)
    session_store.add_message(req.session_id, "model", message)
    logger.info("Persisted session messages: session_id=%s", req.session_id)

    map_pins = None
    if completion.map_pins:
        from app.models import MapPin
        map_pins = [MapPin(**p) for p in completion.map_pins]

    if user_intent == _INTENT_ROUTE:
        map_pins = None

    return ChatResponse(
        session_id=req.session_id,
        message=message,
        route_action=route_action,
        map_pins=map_pins,
        response_intent=user_intent,
    )
