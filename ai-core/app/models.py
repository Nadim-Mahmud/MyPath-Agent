from __future__ import annotations
from typing import Optional, Any
from pydantic import BaseModel


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
