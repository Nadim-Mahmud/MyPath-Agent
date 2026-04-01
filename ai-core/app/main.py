import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import ValidationError

from app.exceptions import AiCoreError
from app.models import ChatRequest, ChatResponse
from app import chat_service, session_store

logger = logging.getLogger(__name__)

app = FastAPI(title="Wheelway AI Core")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173"],
    allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)


# ── Global exception handlers ─────────────────────────────────────────────────

@app.exception_handler(AiCoreError)
async def ai_core_error_handler(request: Request, exc: AiCoreError):
    return JSONResponse(status_code=503, content={"error": str(exc)})


@app.exception_handler(ValidationError)
async def validation_error_handler(request: Request, exc: ValidationError):
    return JSONResponse(status_code=422, content={"error": "Invalid request format."})


@app.exception_handler(Exception)
async def unhandled_error_handler(request: Request, exc: Exception):
    logger.error("Unhandled error on %s %s: %s", request.method, request.url.path, exc, exc_info=True)
    return JSONResponse(status_code=500, content={"error": "An unexpected error occurred. Please try again."})


# ── Routes ────────────────────────────────────────────────────────────────────

@app.get("/health")
def health():
    return {"status": "ok", "service": "wheelway-ai-core"}


@app.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest):
    return chat_service.chat(req)


@app.delete("/session/{session_id}")
def delete_session(session_id: str):
    session_store.clear_session(session_id)
    return {"status": "cleared", "session_id": session_id}
