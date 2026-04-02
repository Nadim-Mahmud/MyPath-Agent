import json
import logging
import pathlib
import httpx
from dataclasses import dataclass
from typing import Any

from app.config import GEMINI_API_KEY, GEMINI_MODEL, GEMINI_BASE_URL, MAX_TOOL_ROUNDS
from app.exceptions import GeminiError
from app.mcp.mcp_server import TOOL_DECLARATIONS, execute_tool

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

_SYSTEM_PROMPT = pathlib.Path(__file__).parent.parent / "prompts" / "system_prompt.txt"


@dataclass
class CompletionResult:
    message: str
    route_action: dict[str, Any] | None = None
    map_pins: list[dict[str, Any]] | None = None


def _load_system_prompt() -> str:
    return _SYSTEM_PROMPT.read_text(encoding="utf-8")


def _call_gemini(contents: list[dict]) -> dict:
    if not GEMINI_API_KEY:
        raise GeminiError("AI service is not configured. Please contact support.")

    url = f"{GEMINI_BASE_URL}/models/{GEMINI_MODEL}:generateContent?key={GEMINI_API_KEY}"
    body = {
        "system_instruction": {"parts": [{"text": _load_system_prompt()}]},
        "contents": contents,
        "tools": [{"function_declarations": TOOL_DECLARATIONS}],
    }
    logger.info("Calling Gemini API: model=%s content_messages=%d", GEMINI_MODEL, len(contents))
    try:
        with httpx.Client(timeout=60) as client:
            resp = client.post(url, json=body)
            resp.raise_for_status()
            logger.info("Gemini API call succeeded: status_code=%d", resp.status_code)
            try:
                return resp.json()
            except ValueError as exc:
                logger.error("Gemini API returned non-JSON response: %s", exc)
                raise GeminiError("The AI service returned an unreadable response. Please try again.")
    except httpx.TimeoutException:
        logger.error("Gemini API request timed out")
        raise GeminiError("The AI service took too long to respond. Please try again.")
    except httpx.HTTPStatusError as exc:
        logger.error("Gemini API error: %s %s", exc.response.status_code, exc.response.text)
        raise GeminiError("The AI service is temporarily unavailable. Please try again.")
    except httpx.RequestError as exc:
        logger.error("Gemini API connection error: %s", exc)
        raise GeminiError("Could not reach the AI service. Please check your connection.")


def _extract_text(response: dict) -> str:
    try:
        parts = response["candidates"][0]["content"]["parts"]
        return "".join(p.get("text", "") for p in parts if "text" in p)
    except (KeyError, IndexError) as exc:
        logger.error("Unexpected Gemini response structure: %s", exc)
        raise GeminiError("Received an unexpected response from the AI service.")


def _extract_function_calls(response: dict) -> list[dict]:
    try:
        parts = response["candidates"][0]["content"]["parts"]
        return [p["functionCall"] for p in parts if "functionCall" in p]
    except (KeyError, IndexError):
        return []


def _build_map_pins(accessibility_result: dict[str, Any]) -> list[dict[str, Any]] | None:
    """Convert a get_place_accessibility tool result into a list of MapPin dicts."""
    if not isinstance(accessibility_result, dict) or not accessibility_result.get("found"):
        return None

    pins: list[dict[str, Any]] = []

    # Building-level pin — only if confirmed accessible
    building_lat = accessibility_result.get("lat")
    building_lon = accessibility_result.get("lon")
    if building_lat is not None and building_lon is not None:
        place_tags = accessibility_result.get("place_tags", {})
        wheelchair = place_tags.get("wheelchair", "")
        if "fully" in wheelchair:
            pins.append({
                "lat": building_lat,
                "lng": building_lon,
                "label": accessibility_result.get("place", "Building"),
                "pin_type": "accessible",
            })

    # Entrance pins — only confirmed accessible entrances
    for entrance in accessibility_result.get("entrances", []):
        elat = entrance.get("lat")
        elon = entrance.get("lon")
        if elat is None or elon is None:
            continue
        wheelchair = entrance.get("wheelchair", "")
        if "fully" not in wheelchair:
            continue

        label_parts = ["Accessible entrance"]
        if entrance.get("door"):
            label_parts.append(f"({entrance['door']} door)")
        if entrance.get("ramp"):
            label_parts.append("· ramp")

        pins.append({
            "lat": elat,
            "lng": elon,
            "label": " ".join(label_parts),
            "pin_type": "accessible",
        })

    # Ramp pins
    for ramp in accessibility_result.get("ramps", []):
        rlat = ramp.get("lat")
        rlon = ramp.get("lon")
        if rlat is None or rlon is None:
            continue
        pins.append({
            "lat": rlat,
            "lng": rlon,
            "label": "Wheelchair ramp",
            "pin_type": "ramp",
        })

    return pins if pins else None


def _build_route_action(
    route_call_args: dict[str, Any] | None,
    geocoded_locations: list[dict[str, Any]],
) -> dict[str, Any] | None:
    if not route_call_args:
        return None

    try:
        src_lat = float(route_call_args["src_lat"])
        src_lng = float(route_call_args["src_lon"])
        dest_lat = float(route_call_args["dest_lat"])
        dest_lng = float(route_call_args["dest_lon"])
    except (KeyError, TypeError, ValueError):
        return None

    origin_label = None
    destination_label = None
    if geocoded_locations:
        if len(geocoded_locations) >= 1:
            origin_label = geocoded_locations[0].get("label")
        if len(geocoded_locations) >= 2:
            destination_label = geocoded_locations[1].get("label")

    return {
        "origin": {"lat": src_lat, "lng": src_lng, "label": origin_label},
        "destination": {"lat": dest_lat, "lng": dest_lng, "label": destination_label},
    }


def complete(user_message: str, history: list[dict]) -> CompletionResult:
    contents = list(history) + [{"role": "user", "parts": [{"text": user_message}]}]
    logger.info(
        "Starting completion: history_messages=%d user_message_chars=%d",
        len(history),
        len(user_message),
    )
    last_route_call_args: dict[str, Any] | None = None
    geocoded_locations: list[dict[str, Any]] = []
    map_pins: list[dict[str, Any]] | None = None

    for round_number in range(1, MAX_TOOL_ROUNDS + 1):
        logger.info("Completion round started: round=%d", round_number)
        response = _call_gemini(contents)
        function_calls = _extract_function_calls(response)
        logger.info("Completion round response: round=%d tool_calls=%d", round_number, len(function_calls))

        if not function_calls:
            logger.info("Completion finished without tool calls: round=%d", round_number)
            return CompletionResult(
                message=_extract_text(response),
                route_action=_build_route_action(last_route_call_args, geocoded_locations),
                map_pins=map_pins,
            )

        try:
            model_content = response["candidates"][0]["content"]
        except (KeyError, IndexError) as exc:
            logger.error("Unexpected Gemini response structure in tool loop: %s", exc)
            raise GeminiError("Received an unexpected response from the AI service.")
        contents.append(model_content)

        tool_response_parts = []
        for fc in function_calls:
            tool_name = fc.get("name", "<unknown>")
            logger.info("Executing tool call: round=%d tool=%s", round_number, tool_name)
            try:
                tool_args = fc.get("args", {})
                result = execute_tool(fc["name"], tool_args)
            except Exception as exc:
                logger.error("Tool '%s' execution failed: %s", fc["name"], exc)
                result = {"error": "Tool execution failed"}

            if fc.get("name") == "get_route" and isinstance(fc.get("args"), dict):
                last_route_call_args = fc["args"]
            if fc.get("name") == "geocode_place" and isinstance(result, dict):
                top_result = None
                results = result.get("results")
                if isinstance(results, list) and results:
                    first = results[0]
                    if isinstance(first, dict):
                        top_result = first
                if top_result:
                    geocoded_locations.append(top_result)

            if fc.get("name") == "get_place_accessibility" and isinstance(result, dict):
                pins = _build_map_pins(result)
                if pins:
                    map_pins = pins

            tool_response_parts.append({
                "functionResponse": {
                    "name": fc["name"],
                    "response": {"content": json.dumps(result)},
                }
            })
        contents.append({"role": "user", "parts": tool_response_parts})

    logger.warning("Completion reached max tool rounds: max_rounds=%d", MAX_TOOL_ROUNDS)
    response = _call_gemini(contents)
    return CompletionResult(
        message=_extract_text(response),
        route_action=_build_route_action(last_route_call_args, geocoded_locations),
        map_pins=map_pins,
    )
