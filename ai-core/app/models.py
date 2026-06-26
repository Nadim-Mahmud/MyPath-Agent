from __future__ import annotations
import re
from typing import Optional, Any
from pydantic import BaseModel, field_validator

MAX_MESSAGE_WORDS = 100

# Matches ASCII control characters except tab (\x09) and newline (\x0a, \x0d)
_CONTROL_CHAR_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


class LocationPoint(BaseModel):
    lat: float
    lng: float


class ChatContext(BaseModel):
    user_location: Optional[LocationPoint] = None
    map_center: Optional[LocationPoint] = None
    active_route: Optional[Any] = None


class ChatRequest(BaseModel):
    session_id: str
    message: str
    context: Optional[ChatContext] = None

    @field_validator("message")
    @classmethod
    def validate_message(cls, v: str) -> str:
        # Strip control characters
        v = _CONTROL_CHAR_RE.sub("", v).strip()
        if not v:
            raise ValueError("Message must not be empty.")
        word_count = len(v.split())
        if word_count > MAX_MESSAGE_WORDS:
            raise ValueError(
                f"Message exceeds the {MAX_MESSAGE_WORDS}-word limit ({word_count} words)."
            )
        return v


class RouteLocation(BaseModel):
    lat: float
    lng: float
    label: Optional[str] = None


class RouteAction(BaseModel):
    origin: RouteLocation
    destination: RouteLocation


class MapPin(BaseModel):
    lat: float
    lng: float
    label: str
    pin_type: str  # "accessible" | "ramp"


class ChatResponse(BaseModel):
    session_id: str
    message: str
    route_action: Optional[RouteAction] = None
    map_pins: Optional[list[MapPin]] = None
    response_intent: Optional[str] = None


class GeocodeResult(BaseModel):
    label: str
    lat: float
    lng: float


class GeocodeRequest(BaseModel):
    query: str
    bias_lat: Optional[float] = None
    bias_lon: Optional[float] = None
    limit: int = 5


class GeocodeResponse(BaseModel):
    query: str
    results: list[GeocodeResult]
