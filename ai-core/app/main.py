"""FastAPI application entry point.

Creates the ASGI application, registers middleware, attaches global exception
handlers, and includes the route routers.  Service singletons live in
``app.dependencies`` — this file only wires them into the HTTP layer.
"""

from __future__ import annotations

import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import ValidationError

from app.constants import (
    APP_SERVICE_NAME,
    APP_TITLE,
    CORS_ALLOWED_METHODS,
    CORS_ALLOWED_ORIGINS,
    LOG_FORMAT,
)
from app.exceptions import AiCoreError
from app.routes.chat import router as chat_router
from app.routes.geocode import router as geocode_router

# Configure root logger once at startup
if not logging.getLogger().handlers:
    logging.basicConfig(level=logging.INFO, format=LOG_FORMAT)

logger = logging.getLogger(__name__)

app = FastAPI(title=APP_TITLE)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ALLOWED_ORIGINS,
    allow_methods=CORS_ALLOWED_METHODS,
    allow_headers=["*"],
)

# ── Global exception handlers ─────────────────────────────────────────────────


@app.exception_handler(AiCoreError)
async def ai_core_error_handler(request: Request, exc: AiCoreError) -> JSONResponse:
    return JSONResponse(status_code=503, content={"error": str(exc)})


@app.exception_handler(ValidationError)
async def validation_error_handler(request: Request, exc: ValidationError) -> JSONResponse:  # noqa: ARG001
    return JSONResponse(status_code=422, content={"error": "Invalid request format."})


@app.exception_handler(Exception)
async def unhandled_error_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.error(
        "Unhandled error: method=%s path=%s error=%s",
        request.method,
        request.url.path,
        exc,
        exc_info=True,
    )
    return JSONResponse(
        status_code=500,
        content={"error": "An unexpected error occurred. Please try again."},
    )


# ── Health check ──────────────────────────────────────────────────────────────


@app.get("/health")
def health() -> dict:
    logger.info("Health check requested")
    return {"status": "ok", "service": APP_SERVICE_NAME}


# ── Route routers ─────────────────────────────────────────────────────────────

app.include_router(chat_router)
app.include_router(geocode_router)
