import logging
import re
import asyncio
import httpx

from app.models import ChatRequest, ChatResponse, ChatContext
from app import session_store
from app import gemini_service
from app.mcp.mcp_server import execute_tool

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


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


_CURRENT_LOCATION_PATTERNS = [
    re.compile(r"(?:from\s+)?(?:my|current)\s+location\s+to\s+(.+)", re.IGNORECASE),
    re.compile(r"(?:navigate|route|directions)\s+(?:me\s+)?to\s+(.+)", re.IGNORECASE),
    re.compile(r"to\s+([A-Z][^.!?]+(?:[A-Z][^.!?]*)*)", re.IGNORECASE),
    re.compile(r"\bto\s+(.+)", re.IGNORECASE),
]


def _enrich_message(message: str, context: ChatContext | None) -> str:
    if context is None:
        return message
    lines = [message, "", "[Context]"]
    if context.user_location:
        lines.append(f"User GPS: {context.user_location.lat}, {context.user_location.lng}")
        lines.append("If user asks from current location, use this User GPS as route origin.")
    if context.map_center:
        lines.append(f"Map centre: {context.map_center.lat}, {context.map_center.lng}")
    if context.active_route is not None:
        lines.append("User has active route.")
    return "\n".join(lines)


def _extract_destination_from_message(message: str) -> str | None:
    for pattern in _CURRENT_LOCATION_PATTERNS:
        match = pattern.search(message.strip())
        if not match:
            continue
        candidate = match.group(1).strip(" .,!?")
        if candidate:
            return candidate
    return None


def _try_current_location_route(req: ChatRequest) -> ChatResponse | None:
    if req.context is None or req.context.user_location is None:
        return None

    destination_query = _extract_destination_from_message(req.message)
    if not destination_query:
        return None

    # Try geocoding with more candidates to handle full addresses
    geocoded = execute_tool("geocode_place", {"query": destination_query, "limit": 5})
    if isinstance(geocoded, dict) and geocoded.get("error"):
        return None

    results = geocoded.get("results") if isinstance(geocoded, dict) else None
    if not isinstance(results, list) or not results:
        return None

    src = req.context.user_location

    # Try the top candidates until one produces a successful route
    for candidate in results:
        if not isinstance(candidate, dict):
            continue

        try:
            dest_lat = float(candidate["lat"])
            dest_lng = float(candidate["lng"])
        except (KeyError, TypeError, ValueError):
            continue

        route_result = execute_tool(
            "get_route",
            {
                "src_lat": src.lat,
                "src_lon": src.lng,
                "dest_lat": dest_lat,
                "dest_lon": dest_lng,
            },
        )

        # Check if route succeeded
        if not (isinstance(route_result, dict) and route_result.get("error")):
            destination_label = str(candidate.get("label") or destination_query)
            distance = route_result.get("total_distance_miles") if isinstance(route_result, dict) else None
            eta = route_result.get("estimated_minutes") if isinstance(route_result, dict) else None
            message = (
                f"I found an accessible route from your current location to **{destination_label}**. "
                f"Estimated distance: **{distance} mi**, travel time: **{eta} min**. "
                "I've loaded it on the map for you."
            )

            return ChatResponse(
                session_id=req.session_id,
                message=message,
                route_action={
                    "origin": {"lat": src.lat, "lng": src.lng, "label": "My Location"},
                    "destination": {"lat": dest_lat, "lng": dest_lng, "label": destination_label},
                },
            )

    # All candidates failed to produce a route
    return None


def chat(req: ChatRequest) -> ChatResponse:
    history = session_store.get_history(req.session_id)
    logger.info("Loaded session history: session_id=%s history_messages=%d", req.session_id, len(history))

    fallback_response = _try_current_location_route(req)
    if fallback_response is not None:
        logger.info("Used current-location route fallback: session_id=%s", req.session_id)
        session_store.add_message(req.session_id, "user", req.message)
        session_store.add_message(req.session_id, "model", fallback_response.message)
        return fallback_response

    enriched = _enrich_message(req.message, req.context)
    logger.info(
        "Prepared enriched user message: session_id=%s enriched_chars=%d",
        req.session_id,
        len(enriched),
    )

    completion = gemini_service.complete(enriched, history)
    logger.info(
        "Received model response: session_id=%s reply_chars=%d has_route_action=%s",
        req.session_id,
        len(completion.message),
        completion.route_action is not None,
    )

    # If Gemini succeeded in computing a route (route_action present),
    # but the message is apologetic, override it with a positive message
    message = completion.message
    if completion.route_action:
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
            dest = completion.route_action.get("destination", {})
            dest_label = (dest.get("label") or "").strip()
            # If label is missing, try reverse geocoding
            if not dest_label:
                try:
                    dest_lat = dest.get("lat")
                    dest_lng = dest.get("lng")
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

    return ChatResponse(
        session_id=req.session_id,
        message=message,
        route_action=completion.route_action,
    )
