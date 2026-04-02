"""FastAPI routes for geocoding / place search."""

from __future__ import annotations

import logging

from fastapi import APIRouter

from app.models import GeocodeRequest, GeocodeResponse

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/geocode", response_model=GeocodeResponse)
async def geocode(req: GeocodeRequest) -> GeocodeResponse:
    from app.dependencies import geocoding_service

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
        logger.error("Geocode failed: query=%s error=%s", req.query, exc, exc_info=True)
        return GeocodeResponse(query=req.query, results=[])
