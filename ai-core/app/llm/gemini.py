"""Google Gemini LLM provider.

Implements :class:`~app.llm.base.LLMProvider` using the Gemini
``generateContent`` REST API.  The provider runs an agentic loop that
dispatches MCP tool calls until the model produces a final text reply.
"""

from __future__ import annotations

import json
import logging
import pathlib
from typing import TYPE_CHECKING, Any

import httpx

from app.constants import (
    LLM_TIMEOUT_S,
    TOOL_GET_ROUTE,
    TOOL_GEOCODE_PLACE,
    TOOL_GET_PLACE_ACCESSIBILITY,
    WHEELCHAIR_FULLY_ACCESSIBLE_MARKER,
)
from app.exceptions import GeminiError
from app.llm.base import LLMProvider
from app.llm.types import CompletionResult

if TYPE_CHECKING:
    from app.config import Settings
    from app.mcp.server import MCPServer

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT_PATH: pathlib.Path = (
    pathlib.Path(__file__).parent.parent.parent / "prompts" / "system_prompt.txt"
)


class GeminiProvider(LLMProvider):
    """LLM provider backed by the Google Gemini REST API."""

    def __init__(self, settings: "Settings", mcp_server: "MCPServer") -> None:
        self._settings = settings
        self._mcp_server = mcp_server
        self._system_prompt: str | None = None

    # ------------------------------------------------------------------
    # LLMProvider interface
    # ------------------------------------------------------------------

    def complete(self, user_message: str, history: list[dict]) -> CompletionResult:
        """Run the agentic completion loop until the model stops issuing tool calls."""
        contents = list(history) + [{"role": "user", "parts": [{"text": user_message}]}]
        logger.info(
            "Starting completion: history_messages=%d user_message_chars=%d",
            len(history),
            len(user_message),
        )

        last_route_call_args: dict[str, Any] | None = None
        geocoded_locations: list[dict[str, Any]] = []
        map_pins: list[dict[str, Any]] | None = None

        for round_number in range(1, self._settings.max_tool_rounds + 1):
            logger.info("Completion round started: round=%d", round_number)
            response = self._call_api(contents)
            function_calls = self._extract_function_calls(response)
            logger.info(
                "Completion round response: round=%d tool_calls=%d",
                round_number,
                len(function_calls),
            )

            if not function_calls:
                logger.info("Completion finished: round=%d", round_number)
                return CompletionResult(
                    message=self._extract_text(response),
                    route_action=self._build_route_action(last_route_call_args, geocoded_locations),
                    map_pins=map_pins,
                )

            try:
                model_content = response["candidates"][0]["content"]
            except (KeyError, IndexError) as exc:
                logger.error("Unexpected Gemini response structure in tool loop: %s", exc)
                raise GeminiError("Received an unexpected response from the AI service.")

            contents.append(model_content)

            tool_response_parts: list[dict] = []
            for fc in function_calls:
                tool_name: str = fc.get("name", "<unknown>")
                logger.info("Executing tool call: round=%d tool=%s", round_number, tool_name)
                try:
                    result = self._mcp_server.execute_tool(fc["name"], fc.get("args", {}))
                except Exception as exc:
                    logger.error("Tool '%s' execution failed: %s", tool_name, exc)
                    result = {"error": "Tool execution failed"}

                # Update mutable accumulators based on which tool was called
                if fc.get("name") == TOOL_GET_ROUTE and isinstance(fc.get("args"), dict):
                    last_route_call_args = fc["args"]

                if fc.get("name") == TOOL_GEOCODE_PLACE and isinstance(result, dict):
                    results_list = result.get("results")
                    if isinstance(results_list, list) and results_list:
                        first = results_list[0]
                        if isinstance(first, dict):
                            geocoded_locations.append(first)

                if fc.get("name") == TOOL_GET_PLACE_ACCESSIBILITY and isinstance(result, dict):
                    pins = self._build_map_pins(result)
                    if pins:
                        map_pins = pins

                tool_response_parts.append({
                    "functionResponse": {
                        "name": fc["name"],
                        "response": {"content": json.dumps(result)},
                    }
                })

            contents.append({"role": "user", "parts": tool_response_parts})

        logger.warning(
            "Completion reached max tool rounds: max_rounds=%d",
            self._settings.max_tool_rounds,
        )
        response = self._call_api(contents)
        return CompletionResult(
            message=self._extract_text(response),
            route_action=self._build_route_action(last_route_call_args, geocoded_locations),
            map_pins=map_pins,
        )

    @property
    def tool_declarations(self) -> list[dict]:
        return self._mcp_server.tool_declarations

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _load_system_prompt(self) -> str:
        if self._system_prompt is None:
            self._system_prompt = _SYSTEM_PROMPT_PATH.read_text(encoding="utf-8")
        return self._system_prompt

    def _call_api(self, contents: list[dict]) -> dict:
        if not self._settings.gemini_api_key:
            raise GeminiError("AI service is not configured. Please contact support.")

        url = f"{self._settings.gemini_generate_url}?key={self._settings.gemini_api_key}"
        body = {
            "system_instruction": {"parts": [{"text": self._load_system_prompt()}]},
            "contents": contents,
            "tools": [{"function_declarations": self.tool_declarations}],
        }
        logger.info(
            "Calling Gemini API: model=%s content_messages=%d",
            self._settings.gemini_model,
            len(contents),
        )
        try:
            with httpx.Client(timeout=LLM_TIMEOUT_S) as client:
                resp = client.post(url, json=body)
                resp.raise_for_status()
                try:
                    return resp.json()
                except ValueError as exc:
                    logger.error("Gemini API returned non-JSON response: %s", exc)
                    raise GeminiError(
                        "The AI service returned an unreadable response. Please try again."
                    )
        except httpx.TimeoutException:
            logger.error("Gemini API request timed out")
            raise GeminiError("The AI service took too long to respond. Please try again.")
        except httpx.HTTPStatusError as exc:
            logger.error(
                "Gemini API HTTP error: status=%d body=%s",
                exc.response.status_code,
                exc.response.text,
            )
            raise GeminiError("The AI service is temporarily unavailable. Please try again.")
        except httpx.RequestError as exc:
            logger.error("Gemini API connection error: %s", exc)
            raise GeminiError("Could not reach the AI service. Please check your connection.")

    @staticmethod
    def _extract_text(response: dict) -> str:
        try:
            parts = response["candidates"][0]["content"]["parts"]
            return "".join(p.get("text", "") for p in parts if "text" in p)
        except (KeyError, IndexError) as exc:
            logger.error("Unexpected Gemini response structure: %s", exc)
            raise GeminiError("Received an unexpected response from the AI service.")

    @staticmethod
    def _extract_function_calls(response: dict) -> list[dict]:
        try:
            parts = response["candidates"][0]["content"]["parts"]
            return [p["functionCall"] for p in parts if "functionCall" in p]
        except (KeyError, IndexError):
            return []

    @staticmethod
    def _build_map_pins(accessibility_result: dict[str, Any]) -> list[dict[str, Any]] | None:
        """Convert a ``get_place_accessibility`` result into a list of MapPin dicts."""
        if not isinstance(accessibility_result, dict) or not accessibility_result.get("found"):
            return None

        pins: list[dict[str, Any]] = []

        building_lat = accessibility_result.get("lat")
        building_lon = accessibility_result.get("lon")
        if building_lat is not None and building_lon is not None:
            place_tags = accessibility_result.get("place_tags", {})
            wheelchair = place_tags.get("wheelchair", "")
            if WHEELCHAIR_FULLY_ACCESSIBLE_MARKER in wheelchair:
                pins.append({
                    "lat": building_lat,
                    "lng": building_lon,
                    "label": accessibility_result.get("place", "Building"),
                    "pin_type": "accessible",
                })

        for entrance in accessibility_result.get("entrances", []):
            elat, elon = entrance.get("lat"), entrance.get("lon")
            if elat is None or elon is None:
                continue
            wheelchair = entrance.get("wheelchair", "")
            if WHEELCHAIR_FULLY_ACCESSIBLE_MARKER not in wheelchair:
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

        for ramp in accessibility_result.get("ramps", []):
            rlat, rlon = ramp.get("lat"), ramp.get("lon")
            if rlat is None or rlon is None:
                continue
            pins.append({
                "lat": rlat,
                "lng": rlon,
                "label": "Wheelchair ramp",
                "pin_type": "ramp",
            })

        return pins if pins else None

    @staticmethod
    def _build_route_action(
        route_call_args: dict[str, Any] | None,
        geocoded_locations: list[dict[str, Any]],
    ) -> dict[str, Any] | None:
        """Reconstruct the route_action dict from the last get_route call arguments."""
        if not route_call_args:
            return None

        try:
            src_lat = float(route_call_args["src_lat"])
            src_lng = float(route_call_args["src_lon"])
            dest_lat = float(route_call_args["dest_lat"])
            dest_lng = float(route_call_args["dest_lon"])
        except (KeyError, TypeError, ValueError):
            return None

        origin_label = geocoded_locations[0].get("label") if len(geocoded_locations) >= 1 else None
        destination_label = (
            geocoded_locations[1].get("label") if len(geocoded_locations) >= 2 else None
        )

        return {
            "origin": {"lat": src_lat, "lng": src_lng, "label": origin_label},
            "destination": {"lat": dest_lat, "lng": dest_lng, "label": destination_label},
        }
