"""FastAPI routes for chat and session management."""

from __future__ import annotations

import logging

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app.exceptions import AiCoreError
from app.models import ChatRequest, ChatResponse

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest) -> ChatResponse:
    from app.dependencies import chat_service

    logger.info(
        "Chat request received: session_id=%s message_chars=%d has_context=%s",
        req.session_id,
        len(req.message),
        req.context is not None,
    )
    try:
        response = chat_service.chat(req)
        logger.info(
            "Chat request succeeded: session_id=%s reply_chars=%d",
            req.session_id,
            len(response.message),
        )
        return response
    except AiCoreError:
        logger.warning("Chat request failed with AiCoreError: session_id=%s", req.session_id)
        raise
    except Exception as exc:
        logger.error("Unexpected error in /chat: %s", exc, exc_info=True)
        raise AiCoreError(f"Unexpected error: {exc}") from exc


@router.delete("/session/{session_id}")
def delete_session(session_id: str) -> JSONResponse:
    from app.dependencies import session_store

    logger.info("Clearing session: session_id=%s", session_id)
    session_store.clear_session(session_id)
    return JSONResponse(content={"status": "cleared", "session_id": session_id})
