class AiCoreError(Exception):
    """Base exception for user-facing errors. Message is safe to return to clients."""


class GeminiError(AiCoreError):
    pass


class RoutingError(AiCoreError):
    pass
