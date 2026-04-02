"""Custom exception hierarchy for the AI-core service.

All :class:`AiCoreError` subclasses carry a message that is safe to return to
API clients.  Internal-only failures should propagate as standard Python
exceptions and be caught by the global handler in ``main.py``.
"""


class AiCoreError(Exception):
    """Base exception for user-facing errors.  Message is safe to surface to clients."""


class LLMError(AiCoreError):
    """Raised when the language-model provider returns an error or is unreachable."""


class GeminiError(LLMError):
    """Gemini-specific LLM errors."""


class RoutingError(AiCoreError):
    """Raised when the wheelchair routing service returns an error or is unreachable."""


class GeocodingError(AiCoreError):
    """Raised when a geocoding request fails in an unrecoverable way."""
