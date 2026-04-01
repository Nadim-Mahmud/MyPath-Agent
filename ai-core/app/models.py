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


class ChatResponse(BaseModel):
    session_id: str
    message: str
