import json
import logging
import pathlib
import httpx

from app.config import GEMINI_API_KEY, GEMINI_MODEL, GEMINI_BASE_URL, MAX_TOOL_ROUNDS
from app.exceptions import GeminiError
from app.mcp.mcp_server import TOOL_DECLARATIONS, execute_tool

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = pathlib.Path(__file__).parent.parent / "prompts" / "system_prompt.txt"


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
    try:
        with httpx.Client(timeout=60) as client:
            resp = client.post(url, json=body)
            resp.raise_for_status()
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


def complete(user_message: str, history: list[dict]) -> str:
    contents = list(history) + [{"role": "user", "parts": [{"text": user_message}]}]

    for _ in range(MAX_TOOL_ROUNDS):
        response = _call_gemini(contents)
        function_calls = _extract_function_calls(response)

        if not function_calls:
            return _extract_text(response)

        try:
            model_content = response["candidates"][0]["content"]
        except (KeyError, IndexError) as exc:
            logger.error("Unexpected Gemini response structure in tool loop: %s", exc)
            raise GeminiError("Received an unexpected response from the AI service.")
        contents.append(model_content)

        tool_response_parts = []
        for fc in function_calls:
            try:
                result = execute_tool(fc["name"], fc.get("args", {}))
            except Exception as exc:
                logger.error("Tool '%s' execution failed: %s", fc["name"], exc)
                result = {"error": "Tool execution failed"}
            tool_response_parts.append({
                "functionResponse": {
                    "name": fc["name"],
                    "response": {"content": json.dumps(result)},
                }
            })
        contents.append({"role": "user", "parts": tool_response_parts})

    response = _call_gemini(contents)
    return _extract_text(response)
