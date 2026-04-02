"""Application settings loaded from environment variables.

Import the module-level ``settings`` singleton wherever configuration is needed.
To add a new setting, add a field to :class:`Settings` and populate it in
:func:`load_settings`.
"""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    """Immutable configuration populated from environment variables at startup."""

    gemini_api_key: str
    gemini_model: str
    gemini_base_url: str
    routing_server_url: str
    routing_api_key: str | None
    max_history_messages: int
    max_tool_rounds: int

    @property
    def gemini_generate_url(self) -> str:
        """Fully-qualified Gemini generateContent endpoint (without the API key)."""
        return f"{self.gemini_base_url}/models/{self.gemini_model}:generateContent"


def load_settings() -> Settings:
    """Read settings from environment variables, applying sensible defaults."""
    return Settings(
        gemini_api_key=os.environ.get("GEMINI_API_KEY", ""),
        gemini_model=os.environ.get("GEMINI_MODEL", "gemini-3.1-flash-lite-preview"),
        gemini_base_url=os.environ.get(
            "GEMINI_BASE_URL",
            "https://generativelanguage.googleapis.com/v1beta",
        ),
        routing_server_url=os.environ.get("ROUTING_SERVER_URL", "http://routing-server:8080"),
        routing_api_key=os.environ.get("ROUTING_API_KEY"),
        max_history_messages=int(os.environ.get("MAX_HISTORY_MESSAGES", "20")),
        max_tool_rounds=int(os.environ.get("MAX_TOOL_ROUNDS", "5")),
    )


# Module-level singleton — import ``settings`` wherever configuration is needed.
settings: Settings = load_settings()
