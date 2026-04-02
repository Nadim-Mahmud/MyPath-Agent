"""User-intent detection and message analysis utilities."""

from __future__ import annotations

import re

from app.constants import (
    INTENT_ACCESSIBILITY,
    INTENT_GENERAL,
    INTENT_ROUTE,
    NEGATIVE_MESSAGE_FAILURE_KEYWORDS,
    NEGATIVE_MESSAGE_PHRASES,
)


class IntentDetector:
    """Classify user messages by intent and extract structured information."""

    # Compiled regex patterns (class-level, compiled once)
    _ROUTE_PATTERNS: tuple[re.Pattern, ...] = (
        re.compile(r"\b(route|directions|navigate|navigation|take me to|way to)\b", re.IGNORECASE),
        re.compile(r"\bfrom\b.+\bto\b", re.IGNORECASE),
        re.compile(r"\bhow\s+do\s+i\s+get\s+to\b", re.IGNORECASE),
    )

    _ACCESSIBILITY_PATTERNS: tuple[re.Pattern, ...] = (
        re.compile(r"\b(accessible|accessibility|wheelchair)\b", re.IGNORECASE),
        re.compile(r"\b(ramp|entrance|door|elevator|lift|curb|kerb|step)\b", re.IGNORECASE),
        re.compile(r"\bis\b.+\baccessible\b", re.IGNORECASE),
    )

    _EXPLICIT_ROUTE_PATTERN: re.Pattern = re.compile(
        r"\b(from\b.+\bto\b|route|directions|navigate)\b", re.IGNORECASE
    )

    # Patterns for extracting a destination from common phrasings
    _DESTINATION_PATTERNS: tuple[re.Pattern, ...] = (
        re.compile(r"(?:from\s+)?(?:my|current)\s+location\s+to\s+(.+)", re.IGNORECASE),
        re.compile(r"(?:navigate|route|directions)\s+(?:me\s+)?to\s+(.+)", re.IGNORECASE),
        re.compile(r"to\s+([A-Z][^.!?]+(?:[A-Z][^.!?]*)*)", re.IGNORECASE),
        re.compile(r"\bto\s+(.+)", re.IGNORECASE),
        re.compile(
            r"(?:to|route to|navigate to)?\s*"
            r"(.+?(?:street|st|avenue|ave|road|rd|boulevard|blvd|drive|dr|building).+)",
            re.IGNORECASE,
        ),
    )

    def detect_intent(self, message: str) -> str:
        """Return one of the ``INTENT_*`` constants for the given message."""
        text = (message or "").strip()
        if not text:
            return INTENT_GENERAL

        has_route = any(p.search(text) for p in self._ROUTE_PATTERNS)
        has_accessibility = any(p.search(text) for p in self._ACCESSIBILITY_PATTERNS)

        if has_route and not has_accessibility:
            return INTENT_ROUTE
        if has_accessibility and not has_route:
            return INTENT_ACCESSIBILITY
        if has_route and has_accessibility:
            if self._EXPLICIT_ROUTE_PATTERN.search(text):
                return INTENT_ROUTE
            return INTENT_ACCESSIBILITY
        return INTENT_GENERAL

    def extract_destination(self, message: str) -> str | None:
        """Return the destination string mentioned in *message*, or ``None``."""
        for pattern in self._DESTINATION_PATTERNS:
            match = pattern.search(message.strip())
            if match:
                candidate = match.group(1).strip(" .,!?")
                if candidate:
                    return candidate
        return None

    @staticmethod
    def is_negative_geocoding_message(text: str) -> bool:
        """Return ``True`` if *text* looks like a failed geocoding/routing reply."""
        lower = text.lower()
        has_failure_context = any(kw in lower for kw in NEGATIVE_MESSAGE_FAILURE_KEYWORDS)
        has_negative = any(phrase in lower for phrase in NEGATIVE_MESSAGE_PHRASES)
        return has_failure_context and has_negative
