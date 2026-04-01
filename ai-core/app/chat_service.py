from app.models import ChatRequest, ChatResponse, ChatContext
from app import session_store
from app import gemini_service


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
    enriched = _enrich_message(req.message, req.context)
    reply = gemini_service.complete(enriched, history)

    session_store.add_message(req.session_id, "user", enriched)
    session_store.add_message(req.session_id, "model", reply)

    return ChatResponse(session_id=req.session_id, message=reply)
