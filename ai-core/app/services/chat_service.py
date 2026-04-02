"""Core chat orchestration service.

:class:`ChatService` is the main entry point for processing a
:class:`~app.models.ChatRequest`.  It:

* Detects user intent (route / accessibility / general).
* Attempts a fast-path route resolution without calling the LLM.
* Enriches the user message with GPS context and intent hints.
* Delegates to the :class:`~app.llm.base.LLMProvider` for the agentic loop.
* Persists the conversation turn to :class:`~app.services.session_store.SessionStore`.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
from typing import TYPE_CHECKING

import httpx

from app.constants import (
    APOLOGETIC_PHRASES,
    CONTEXT_BLOCK_MARKER,
    INTENT_ACCESSIBILITY,
    INTENT_ROUTE,
    MY_LOCATION_LABEL,
    NOMINATIM_BASE_URL,
    NOMINATIM_REVERSE_PATH,
    NOMINATIM_USER_AGENT,
    PRE_RESOLVED_MARKER,
    REVERSE_GEOCODE_TIMEOUT_S,
    ROUTE_DESTINATION_FALLBACK_LABEL,
    ROUTE_FALLBACK_MESSAGE_TEMPLATE,
    ROUTE_FOUND_MARKER_PREFIX,
    ROUTE_NOTE_TEMPLATE,
    ROUTE_SUCCESS_MESSAGE_TEMPLATE,
)
from app.models import ChatContext, ChatRequest, ChatResponse, MapPin

if TYPE_CHECKING:
    from app.llm.base import LLMProvider
    from app.mcp.server import MCPServer
    from app.services.intent_detector import IntentDetector
    from app.services.session_store import SessionStore

logger = logging.getLogger(__name__)

_NOMINATIM_REVERSE_URL: str = NOMINATIM_BASE_URL + NOMINATIM_REVERSE_PATH
_NOMINATIM_HEADERS: dict[str, str] = {"User-Agent": NOMINATIM_USER_AGENT}

_MAX_CONTEXT_ROUTE_SEGMENTS: int = 40
_MAX_FOCUSED_HISTORY_MESSAGES: int = 6

_STREET_MARKER_PATTERN: re.Pattern = re.compile(
    r"\d+\s+(street|st|avenue|ave|road|rd|boulevard|blvd|drive|dr|building)",
    re.IGNORECASE,
)

_ACCESSIBLE_ENTRANCE_LABEL: str = "Accessible entrance"
_FULLY_ACCESSIBLE_MARKER: str = "fully"  # substring checked against wheelchair label


class ChatService:
    """Orchestrates a single chat turn from request to response."""

    def __init__(
        self,
        llm: "LLMProvider",
        session_store: "SessionStore",
        mcp_server: "MCPServer",
        intent_detector: "IntentDetector",
    ) -> None:
        self._llm = llm
        self._session_store = session_store
        self._mcp_server = mcp_server
        self._intent_detector = intent_detector

    def chat(self, request: ChatRequest) -> ChatResponse:
        """Process *request* and return a :class:`ChatResponse`."""
        history = self._session_store.get_history(request.session_id)
        intent = self._intent_detector.detect_intent(request.message)
        logger.info(
            "Loaded session history: session_id=%s messages=%d intent=%s",
            request.session_id, len(history), intent,
        )

        is_retry = self._detect_retry_after_failure(request, history, intent)
        focused_history = self._build_focused_history(
            history, strip_negative_geocoding=is_retry
        )
        logger.info(
            "Prepared focused history: session_id=%s focused=%d stripped_negative=%s",
            request.session_id, len(focused_history), is_retry,
        )

        # Fast-path: try routing directly without the LLM for common phrasings
        if intent == INTENT_ROUTE:
            fast_response, pre_resolved_ctx = self._try_current_location_route(request)
            if fast_response is not None:
                logger.info("Used fast-path route: session_id=%s", request.session_id)
                self._persist_fast_route(request, fast_response)
                return fast_response
        else:
            pre_resolved_ctx = None

        enriched = self._enrich_message(request.message, request.context, intent)
        if pre_resolved_ctx:
            enriched += PRE_RESOLVED_MARKER + pre_resolved_ctx

        logger.info(
            "Calling LLM: session_id=%s enriched_chars=%d",
            request.session_id, len(enriched),
        )
        completion = self._llm.complete(enriched, focused_history)
        logger.info(
            "LLM response received: session_id=%s reply_chars=%d has_route=%s",
            request.session_id, len(completion.message), completion.route_action is not None,
        )

        message = completion.message
        route_action = completion.route_action if intent != INTENT_ACCESSIBILITY else None
        map_pins = None if intent == INTENT_ROUTE else completion.map_pins

        # Override apologetic messages when a route was actually found
        if route_action and self._is_apologetic(message):
            message = self._build_positive_route_message(route_action)
            logger.info("Overrode apologetic message with route success: session_id=%s", request.session_id)

        self._session_store.add_message(request.session_id, "user", enriched)
        self._session_store.add_message(request.session_id, "model", message)
        logger.info("Persisted session messages: session_id=%s", request.session_id)

        return ChatResponse(
            session_id=request.session_id,
            message=message,
            route_action=route_action,
            map_pins=[MapPin(**p) for p in map_pins] if map_pins else None,
            response_intent=intent,
        )

    # ------------------------------------------------------------------
    # Fast-path routing
    # ------------------------------------------------------------------

    def _try_current_location_route(
        self, request: ChatRequest
    ) -> tuple[ChatResponse | None, str | None]:
        """Attempt to resolve and route without the LLM.

        Returns:
            ``(ChatResponse, None)``        — route found; use it directly.
            ``(None, pre_resolved_ctx)``    — place resolved but routing failed;
                                             ctx string tells the LLM what coords
                                             to use so it can skip geocoding.
            ``(None, None)``               — could not even resolve the place.
        """
        if request.context is None or request.context.user_location is None:
            return None, None

        destination_query = self._intent_detector.extract_destination(request.message)
        if not destination_query:
            return None, None

        src = request.context.user_location
        has_street_markers = bool(_STREET_MARKER_PATTERN.search(destination_query))

        building_lat: float | None = None
        building_lng: float | None = None
        destination_label: str = destination_query
        accessible_entrance_coords: list[tuple[float, float, str]] = []
        accessibility_summary: str = ""

        if not has_street_markers:
            accessibility = self._mcp_server.execute_tool(
                "get_place_accessibility",
                {"place_name": destination_query, "bias_lat": src.lat, "bias_lon": src.lng},
            )
            if isinstance(accessibility, dict) and accessibility.get("found"):
                building_lat = float(accessibility["lat"])
                building_lng = float(accessibility["lon"])
                destination_label = str(accessibility.get("place") or destination_query)

                for entrance in accessibility.get("entrances", []):
                    wheelchair = entrance.get("wheelchair", "")
                    elat, elon = entrance.get("lat"), entrance.get("lon")
                    if _FULLY_ACCESSIBLE_MARKER in wheelchair and elat is not None and elon is not None:
                        accessible_entrance_coords.append(
                            (float(elat), float(elon), destination_label + " (accessible entrance)")
                        )

                entrance_pairs = [(c[0], c[1]) for c in accessible_entrance_coords]
                accessibility_summary = (
                    f'Destination "{destination_query}" already resolved to '
                    f"lat={building_lat:.5f}, lng={building_lng:.5f}. "
                    + (
                        f"Accessible entrances at: {entrance_pairs}. "
                        if entrance_pairs
                        else "No accessible entrances found in OSM. "
                    )
                    + "do NOT call geocode_place or get_place_accessibility again. "
                    "Call get_route directly using the coordinates above."
                )
        else:
            geocoded = self._mcp_server.execute_tool(
                "geocode_place", {"query": destination_query, "limit": 10}
            )
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

        # Always add the centroid as a final fallback after accessible entrances
        coords_to_try = accessible_entrance_coords + [(building_lat, building_lng, destination_label)]

        for dest_lat, dest_lng, label in coords_to_try:
            route_result = self._mcp_server.execute_tool(
                "get_route",
                {"src_lat": src.lat, "src_lon": src.lng, "dest_lat": dest_lat, "dest_lon": dest_lng},
            )
            if isinstance(route_result, dict) and not route_result.get("error"):
                distance = route_result.get("total_distance_miles")
                eta = route_result.get("estimated_minutes")
                return ChatResponse(
                    session_id=request.session_id,
                    message=ROUTE_FALLBACK_MESSAGE_TEMPLATE.format(
                        destination=label, distance=distance, eta=eta
                    ),
                    route_action={
                        "origin": {"lat": src.lat, "lng": src.lng, "label": MY_LOCATION_LABEL},
                        "destination": {"lat": dest_lat, "lng": dest_lng, "label": label},
                    },
                ), None

        return None, accessibility_summary or None

    def _persist_fast_route(self, request: ChatRequest, response: ChatResponse) -> None:
        dest_lat, dest_lng, dest_label = self._route_destination_fields(response.route_action)
        route_note = ROUTE_NOTE_TEMPLATE.format(
            prefix=ROUTE_FOUND_MARKER_PREFIX,
            destination=dest_label or "the destination",
            lat=dest_lat,
            lng=dest_lng,
        )
        self._session_store.add_message(request.session_id, "user", request.message)
        self._session_store.add_message(
            request.session_id, "model", route_note + " " + response.message
        )

    # ------------------------------------------------------------------
    # Message enrichment / history utilities
    # ------------------------------------------------------------------

    def _enrich_message(
        self, message: str, context: ChatContext | None, intent: str
    ) -> str:
        """Append intent hints and GPS context to *message* before sending to the LLM."""
        if context is None:
            if intent == INTENT_ROUTE:
                return message + "\n\n[Intent] route request. Prioritize routing actions."
            if intent == INTENT_ACCESSIBILITY:
                return (
                    message
                    + "\n\n[Intent] accessibility information request. "
                    "Provide accessibility details; do not create a route unless explicitly asked."
                )
            return message

        if intent == INTENT_ROUTE:
            intent_handling = (
                "[Intent handling] User is asking for route planning. Prioritize route computation."
            )
        elif intent == INTENT_ACCESSIBILITY:
            intent_handling = (
                "[Intent handling] User is asking for accessibility information. "
                "Do not create a route unless explicitly requested."
            )
        else:
            intent_handling = (
                "[Intent handling] Answer directly. Only route when explicitly requested."
            )

        lines = [
            message,
            "",
            "[Instruction] Prioritize this latest user request. Use earlier history only for short continuity.",
            f"[Intent] {intent}",
            intent_handling,
            "",
            "[Context]",
        ]

        if context.user_location:
            lines.append(f"User GPS: {context.user_location.lat}, {context.user_location.lng}")
            lines.append("If user asks from current location, use this User GPS as route origin.")
        if context.map_center:
            lines.append(f"Map centre: {context.map_center.lat}, {context.map_center.lng}")

        if context.active_route is not None:
            compact_route = self._compact_active_route(context.active_route)
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

    def _build_focused_history(
        self, history: list[dict], strip_negative_geocoding: bool = False
    ) -> list[dict]:
        """Return the most recent messages, optionally stripping a failed geocoding reply."""
        if strip_negative_geocoding:
            history = self._strip_negative_geocoding_history(history)

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
                    text = self._strip_context_block(text)
                sanitized_parts.append({"text": text})

            if sanitized_parts:
                sanitized.append({"role": role, "parts": sanitized_parts})

        return sanitized

    def _strip_negative_geocoding_history(self, history: list[dict]) -> list[dict]:
        """Remove the most recent negative geocoding reply from *history* if present."""
        for i in range(len(history) - 1, -1, -1):
            entry = history[i]
            if entry.get("role") == "model":
                parts = entry.get("parts", [])
                if parts and isinstance(parts[0], dict):
                    text = parts[0].get("text", "")
                    if self._intent_detector.is_negative_geocoding_message(text):
                        logger.info("Stripping negative geocoding message from retry history")
                        return history[:i] + history[i + 1:]
                break
        return history

    def _detect_retry_after_failure(
        self, request: ChatRequest, history: list[dict], intent: str
    ) -> bool:
        """Return ``True`` if the user is retrying after a failed geocoding attempt."""
        if intent != INTENT_ROUTE or len(history) < 2:
            return False
        for i in range(len(history) - 1, -1, -1):
            if history[i].get("role") == "model":
                parts = history[i].get("parts", [])
                if parts and isinstance(parts[0], dict):
                    model_text = parts[0].get("text", "")
                    if self._intent_detector.is_negative_geocoding_message(model_text):
                        if self._intent_detector.extract_destination(request.message):
                            logger.info(
                                "Detected retry after geocoding failure: session_id=%s",
                                request.session_id,
                            )
                            return True
                break
        return False

    # ------------------------------------------------------------------
    # Response helpers
    # ------------------------------------------------------------------

    def _build_positive_route_message(self, route_action: object) -> str:
        dest_lat, dest_lng, dest_label = self._route_destination_fields(route_action)
        if not dest_label and dest_lat is not None and dest_lng is not None:
            try:
                dest_label = asyncio.run(self._reverse_geocode_label(dest_lat, dest_lng))
            except Exception as exc:
                logger.warning("Reverse geocode failed: %s", exc)
        return ROUTE_SUCCESS_MESSAGE_TEMPLATE.format(
            destination=dest_label or ROUTE_DESTINATION_FALLBACK_LABEL
        )

    @staticmethod
    def _is_apologetic(message: str) -> bool:
        lower = message.lower()
        return any(phrase in lower for phrase in APOLOGETIC_PHRASES)

    @staticmethod
    async def _reverse_geocode_label(lat: float, lng: float) -> str:
        """Resolve coordinates to a human-readable address label."""
        try:
            async with httpx.AsyncClient(timeout=REVERSE_GEOCODE_TIMEOUT_S) as client:
                resp = await client.get(
                    f"{_NOMINATIM_REVERSE_URL}?lat={lat}&lon={lng}&format=json",
                    headers=_NOMINATIM_HEADERS,
                )
                if resp.status_code == 200:
                    data = resp.json()
                    display_name = data.get("display_name", "")
                    if isinstance(display_name, str) and display_name.strip():
                        return display_name.strip()
        except Exception as exc:
            logger.debug("Reverse geocode failed: %s", exc)
        return f"{lat:.5f}, {lng:.5f}"

    # ------------------------------------------------------------------
    # Route compaction (for active-route context)
    # ------------------------------------------------------------------

    @staticmethod
    def _compact_active_route(active_route: object) -> dict | None:
        """Compress a full route object into a summary safe to embed in the LLM context."""
        if not isinstance(active_route, dict):
            return None

        routes = active_route.get("routes")
        if not isinstance(routes, dict):
            return None

        points = routes.get("points")
        if not isinstance(points, list) or not points:
            return None

        compact_segments: list[dict] = []
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

            compact_segments.append({
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
            })

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

    # ------------------------------------------------------------------
    # Utility helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _strip_context_block(text: str) -> str:
        """Remove the ``[Context]`` block appended by :meth:`_enrich_message`."""
        if CONTEXT_BLOCK_MARKER in text:
            return text.split(CONTEXT_BLOCK_MARKER, 1)[0].strip()
        return text

    @staticmethod
    def _route_destination_fields(
        route_action: object,
    ) -> tuple[float | None, float | None, str | None]:
        """Extract (lat, lng, label) from a dict- or model-based route action."""
        if route_action is None:
            return None, None, None

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
