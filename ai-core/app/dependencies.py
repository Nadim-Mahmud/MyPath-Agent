"""Application-level service singletons (dependency container).

All long-lived service instances are created here once at import time.
Routes and other consumers import the named instances directly:

    from app.dependencies import chat_service, session_store, geocoding_service

To swap a provider (e.g. replace Gemini with another LLM), change the
``llm_provider`` assignment below — no other files need touching.
"""

from __future__ import annotations

from app.config import settings
from app.constants import RATE_LIMIT_MAX_REQUESTS, RATE_LIMIT_WINDOW_SECONDS
from app.llm.base import LLMProvider
from app.llm.gemini import GeminiProvider
from app.mcp.server import MCPServer
from app.services.chat_service import ChatService
from app.services.geocoding_service import GeocodingService
from app.services.intent_detector import IntentDetector
from app.services.rate_limiter import RateLimiter
from app.services.safety_guard import SafetyGuard
from app.services.session_store import SessionStore

# Leaf services (no inter-service dependencies)
session_store: SessionStore = SessionStore(max_messages=settings.max_history_messages)
geocoding_service: GeocodingService = GeocodingService()
intent_detector: IntentDetector = IntentDetector()
safety_guard: SafetyGuard = SafetyGuard()
rate_limiter: RateLimiter = RateLimiter(
    max_requests=RATE_LIMIT_MAX_REQUESTS,
    window_seconds=RATE_LIMIT_WINDOW_SECONDS,
)

# MCP server depends on routing config and geocoding
mcp_server: MCPServer = MCPServer(
    settings=settings,
    geocoding_service=geocoding_service,
)

# LLM provider depends on settings and the MCP server
if settings.llm_provider == "ollama":
    from app.llm.ollama import OllamaProvider
    llm_provider: LLMProvider = OllamaProvider(settings=settings, mcp_server=mcp_server)
else:
    llm_provider: LLMProvider = GeminiProvider(settings=settings, mcp_server=mcp_server)

# Top-level chat orchestrator
chat_service: ChatService = ChatService(
    llm=llm_provider,
    session_store=session_store,
    mcp_server=mcp_server,
    intent_detector=intent_detector,
)
