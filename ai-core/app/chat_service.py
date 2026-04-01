import logging

from app.models import ChatRequest, ChatResponse, ChatContext
from app import session_store
from app import gemini_service

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def _enrich_message(message: str, context: ChatContext | None) -> str:
    if context is None:
        return message
    lines = [message, "", "[Context]"]
    if context.user_location:
        lines.append(f"User GPS: {context.user_location.lat}, {context.user_location.lng}")
    if context.map_center:
        lines.append(f"Map centre: {context.map_center.lat}, {context.map_center.lng}")
    if context.active_route is not None:
        lines.append("User has active route.")
    return "\n".join(lines)


def chat(req: ChatRequest) -> ChatResponse:
    history = session_store.get_history(req.session_id)
    logger.info("Loaded session history: session_id=%s history_messages=%d", req.session_id, len(history))

    enriched = _enrich_message(req.message, req.context)
    logger.info(
        "Prepared enriched user message: session_id=%s enriched_chars=%d",
        req.session_id,
        len(enriched),
    )

    reply = gemini_service.complete(enriched, history)
    logger.info("Received model response: session_id=%s reply_chars=%d", req.session_id, len(reply))

    session_store.add_message(req.session_id, "user", enriched)
    session_store.add_message(req.session_id, "model", reply)
    logger.info("Persisted session messages: session_id=%s", req.session_id)

    return ChatResponse(session_id=req.session_id, message=reply)
