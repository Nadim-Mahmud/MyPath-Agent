"""Data types shared between the LLM abstraction layer and its callers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class CompletionResult:
    """Structured result returned by an :class:`LLMProvider` completion call."""

    message: str
    route_action: dict[str, Any] | None = None
    map_pins: list[dict[str, Any]] | None = None
