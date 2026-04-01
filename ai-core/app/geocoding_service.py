import logging
import httpx
from math import radians, cos, sin, asin, sqrt

logger = logging.getLogger(__name__)


def _haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate distance in kilometers between two lat/lon points."""
    lon1, lat1, lon2, lat2 = map(radians, [lon1, lat1, lon2, lat2])
    dlon = lon2 - lon1
    dlat = lat2 - lat1
    a = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
    c = 2 * asin(sqrt(a))
    km = 6371 * c
    return km


def _score_candidate(
    candidate: dict,
    query: str,
    bias_lat: float | None,
    bias_lon: float | None,
) -> tuple[float, dict]:
    """
    Score a geocoding result.
    Returns (score, candidate) where higher score = better match.
    """
    score = 0.0
    label = str(candidate.get("display_name", "")).lower()
    query_lower = query.lower()

    # Exact token match in display name (strong signal)
    if query_lower in label:
        score += 100.0
    # Partial/prefix match
    elif any(q in label for q in query_lower.split()):
        score += 50.0

    # Proximity bonus (closer = better, up to 50 points)
    if bias_lat is not None and bias_lon is not None:
        try:
            candidate_lat = float(candidate.get("lat", 0))
            candidate_lon = float(candidate.get("lon", 0))
            distance_km = _haversine_distance(bias_lat, bias_lon, candidate_lat, candidate_lon)
            proximity_bonus = max(0, 50 - (distance_km / 2))
            score += proximity_bonus
        except (TypeError, ValueError):
            pass

    # Importance class (if available from Nominatim)
    importance = candidate.get("importance", 0)
    if isinstance(importance, (int, float)):
        score += importance * 10

    return (score, candidate)


async def search_places(
    query: str,
    bias_lat: float | None = None,
    bias_lon: float | None = None,
    limit: int = 5,
) -> list[dict]:
    """
    Search for places using Nominatim with importance scoring and proximity bias.

    Args:
        query: Place name or address to search
        bias_lat: Latitude to bias results toward (optional)
        bias_lon: Longitude to bias results toward (optional)
        limit: Max results to return

    Returns:
        List of candidates ranked by relevance: [{"label": str, "lat": float, "lng": float}, ...]
    """
    if not query or not query.strip():
        return []

    query = query.strip()
    limit = max(1, min(int(limit), 10))

    params = {
        "q": query,
        "format": "json",
        "limit": limit * 2,  # Fetch extra to allow scoring/filtering
    }

    # Add viewbox bias if provided (bounds the search geographically)
    if bias_lat is not None and bias_lon is not None:
        # Create a 50km box around the bias point
        box_delta = 0.45  # ~50km in degrees (rough approximation)
        params["viewbox"] = f"{bias_lon - box_delta},{bias_lat - box_delta},{bias_lon + box_delta},{bias_lat + box_delta}"
        params["bounded"] = "0"  # Soft bias, not hard boundary

    headers = {"User-Agent": "Wheelway/1.0 (wheelchair-navigation-ai)"}

    try:
        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.get("https://nominatim.openstreetmap.org/search", params=params, headers=headers)
            resp.raise_for_status()
            raw_results = resp.json()
    except httpx.TimeoutException:
        logger.error("Nominatim request timed out")
        return []
    except httpx.HTTPStatusError as exc:
        logger.error("Nominatim error: %s", exc.response.status_code)
        return []
    except Exception as exc:
        logger.error("Failed to search places: %s", exc)
        return []

    if not isinstance(raw_results, list):
        return []

    # Score and rank candidates
    scored = []
    for item in raw_results:
        if not isinstance(item, dict):
            continue
        try:
            lat = float(item.get("lat", 0))
            lng = float(item.get("lon", 0))
            label = str(item.get("display_name", query))
            score, _ = _score_candidate(item, query, bias_lat, bias_lon)
            scored.append((score, {"label": label, "lat": lat, "lng": lng}))
        except (TypeError, ValueError):
            continue

    # Sort by score descending and return top `limit`
    scored.sort(key=lambda x: x[0], reverse=True)
    results = [candidate for _, candidate in scored[:limit]]

    logger.info("Geocoded '%s' with bias(%s,%s): returned %d candidates", query, bias_lat, bias_lon, len(results))
    return results
