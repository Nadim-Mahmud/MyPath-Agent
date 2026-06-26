"""Ollama local LLM provider.

Uses Ollama's /api/chat endpoint with function-calling support.
Activate by setting LLM_PROVIDER=ollama and OLLAMA_MODEL=<model>.
Tool-calling models recommended: qwen2.5:7b, llama3.1:8b, llama3.2:3b.
"""

from __future__ import annotations

import json
import logging
import pathlib
from typing import TYPE_CHECKING, Any

import httpx

from app.constants import (
    LLM_TIMEOUT_S,
    TOOL_GEOCODE_PLACE,
    TOOL_GET_PLACE_ACCESSIBILITY,
    TOOL_GET_ROUTE,
    WHEELCHAIR_FULLY_ACCESSIBLE_MARKER,
)
from app.llm.base import LLMProvider
from app.llm.types import CompletionResult

if TYPE_CHECKING:
    from app.config import Settings
    from app.mcp.server import MCPServer

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT_PATH: pathlib.Path = (
    pathlib.Path(__file__).parent.parent.parent / "prompts" / "system_prompt.txt"
)


class OllamaError(RuntimeError):
    """Raised when the Ollama backend returns an unexpected response."""


class OllamaProvider(LLMProvider):
    """LLM provider backed by a local Ollama instance."""

    def __init__(self, settings: "Settings", mcp_server: "MCPServer") -> None:
        self._settings = settings
        self._mcp_server = mcp_server
        self._system_prompt: str | None = None

    # ------------------------------------------------------------------
    # LLMProvider interface
    # ------------------------------------------------------------------

    def complete(self, user_message: str, history: list[dict]) -> CompletionResult:
        """Run the agentic tool-calling loop until the model produces a final reply."""
        messages: list[dict] = [{"role": "system", "content": self._load_system_prompt()}]

        # history arrives in Gemini parts format from ChatService._build_focused_history;
        # convert to OpenAI/Ollama role+content format.
        for entry in history:
            role = entry.get("role")
            parts = entry.get("parts", [])
            if role not in ("user", "model") or not isinstance(parts, list) or not parts:
                continue
            text = " ".join(p.get("text", "") for p in parts if isinstance(p, dict) and "text" in p)
            messages.append({
                "role": "assistant" if role == "model" else "user",
                "content": text,
            })

        messages.append({"role": "user", "content": user_message})

        last_route_call_args: dict[str, Any] | None = None
        geocoded_locations: list[dict[str, Any]] = []
        map_pins: list[dict[str, Any]] | None = None

        for round_number in range(1, self._settings.max_tool_rounds + 1):
            logger.info("Ollama completion round: %d", round_number)
            response = self._call_api(messages)
            msg = response.get("message", {})
            tool_calls: list[dict] = msg.get("tool_calls") or []

            if not tool_calls:
                logger.info("Ollama completion finished at round %d", round_number)
                return CompletionResult(
                    message=msg.get("content", ""),
                    route_action=self._build_route_action(last_route_call_args, geocoded_locations),
                    map_pins=map_pins,
                )

            messages.append(msg)

            for tc in tool_calls:
                fn = tc.get("function", {})
                tool_name: str = fn.get("name", "")
                args: Any = fn.get("arguments", {})
                if isinstance(args, str):
                    try:
                        args = json.loads(args)
                    except json.JSONDecodeError:
                        args = {}

                logger.info("Ollama tool call: round=%d tool=%s", round_number, tool_name)
                try:
                    result = self._mcp_server.execute_tool(tool_name, args)
                except Exception as exc:
                    logger.error("Tool '%s' failed: %s", tool_name, exc)
                    result = {"error": "Tool execution failed"}

                if tool_name == TOOL_GET_ROUTE and isinstance(args, dict):
                    last_route_call_args = args

                if tool_name == TOOL_GEOCODE_PLACE and isinstance(result, dict):
                    results_list = result.get("results")
                    if isinstance(results_list, list) and results_list:
                        first = results_list[0]
                        if isinstance(first, dict):
                            geocoded_locations.append(first)

                if tool_name == TOOL_GET_PLACE_ACCESSIBILITY and isinstance(result, dict):
                    pins = self._build_map_pins(result)
                    if pins:
                        map_pins = pins

                messages.append({"role": "tool", "content": json.dumps(result)})

        logger.warning("Ollama reached max tool rounds (%d)", self._settings.max_tool_rounds)
        response = self._call_api(messages)
        msg = response.get("message", {})
        return CompletionResult(
            message=msg.get("content", ""),
            route_action=self._build_route_action(last_route_call_args, geocoded_locations),
            map_pins=map_pins,
        )

    @property
    def tool_declarations(self) -> list[dict]:
        """Convert Gemini-format declarations to Ollama/OpenAI function format."""
        return [
            {
                "type": "function",
                "function": {
                    "name": d["name"],
                    "description": d.get("description", ""),
                    "parameters": d.get("parameters", {}),
                },
            }
            for d in self._mcp_server.tool_declarations
        ]

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _load_system_prompt(self) -> str:
        if self._system_prompt is None:
            self._system_prompt = _SYSTEM_PROMPT_PATH.read_text(encoding="utf-8")
        return self._system_prompt

    def _call_api(self, messages: list[dict]) -> dict:
        url = f"{self._settings.ollama_base_url}/api/chat"
        body = {
            "model": self._settings.ollama_model,
            "messages": messages,
            "tools": self.tool_declarations,
            "stream": False,
        }
        logger.info(
            "Calling Ollama: model=%s messages=%d",
            self._settings.ollama_model,
            len(messages),
        )
        try:
            with httpx.Client(timeout=LLM_TIMEOUT_S) as client:
                resp = client.post(url, json=body)
                resp.raise_for_status()
                try:
                    return resp.json()
                except ValueError as exc:
                    raise OllamaError("Ollama returned non-JSON response") from exc
        except httpx.TimeoutException as exc:
            raise OllamaError("Ollama request timed out") from exc
        except httpx.HTTPStatusError as exc:
            raise OllamaError(
                f"Ollama HTTP {exc.response.status_code}: {exc.response.text[:200]}"
            ) from exc
        except httpx.RequestError as exc:
            raise OllamaError(
                f"Cannot reach Ollama at {self._settings.ollama_base_url}: {exc}"
            ) from exc

    @staticmethod
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
        origin_label = geocoded_locations[0].get("label") if len(geocoded_locations) >= 1 else None
        destination_label = (
            geocoded_locations[1].get("label") if len(geocoded_locations) >= 2 else None
        )
        return {
            "origin": {"lat": src_lat, "lng": src_lng, "label": origin_label},
            "destination": {"lat": dest_lat, "lng": dest_lng, "label": destination_label},
        }

    @staticmethod
    def _build_map_pins(
        accessibility_result: dict[str, Any],
    ) -> list[dict[str, Any]] | None:
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
                "lat": elat, "lng": elon,
                "label": " ".join(label_parts),
                "pin_type": "accessible",
            })
        for ramp in accessibility_result.get("ramps", []):
            rlat, rlon = ramp.get("lat"), ramp.get("lon")
            if rlat is None or rlon is None:
                continue
            pins.append({"lat": rlat, "lng": rlon, "label": "Wheelchair ramp", "pin_type": "ramp"})
        return pins if pins else None
