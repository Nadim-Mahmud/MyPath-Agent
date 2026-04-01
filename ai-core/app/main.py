import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import ValidationError

from app.exceptions import AiCoreError
from app.models import ChatRequest, ChatResponse, GeocodeRequest, GeocodeResponse
from app import chat_service, session_store, geocoding_service

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

if not logging.getLogger().handlers:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )

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
    logger.info("Health check requested")
    return {"status": "ok", "service": "wheelway-ai-core"}


@app.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest):
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


@app.delete("/session/{session_id}")
def delete_session(session_id: str):
    logger.info("Clearing session: session_id=%s", session_id)
    session_store.clear_session(session_id)
    return {"status": "cleared", "session_id": session_id}


@app.post("/geocode", response_model=GeocodeResponse)
async def geocode(req: GeocodeRequest):
    logger.info(
        "Geocode request received: query=%s has_bias=%s limit=%d",
        req.query,
        req.bias_lat is not None and req.bias_lon is not None,
        req.limit,
    )
    try:
        results = await geocoding_service.search_places(
            query=req.query,
            bias_lat=req.bias_lat,
            bias_lon=req.bias_lon,
            limit=req.limit,
        )
        logger.info("Geocode succeeded: query=%s results=%d", req.query, len(results))
        return GeocodeResponse(query=req.query, results=results)
    except Exception as exc:
        logger.error("Geocode failed: %s", exc, exc_info=True)
        return GeocodeResponse(query=req.query, results=[])
