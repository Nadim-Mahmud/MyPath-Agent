"""Geocoding and place-lookup service backed by OpenStreetMap Nominatim."""

from __future__ import annotations

import logging
import re
from math import asin, cos, radians, sin, sqrt

import httpx

from app.constants import (
    GEOCODING_DEFAULT_LIMIT,
    GEOCODING_FETCH_MULTIPLIER,
    GEOCODING_MAX_LIMIT,
    GEOCODING_SCORE_EXACT_MATCH,
    GEOCODING_SCORE_IMPORTANCE_SCALE,
    GEOCODING_SCORE_PARTIAL_MATCH,
    GEOCODING_SCORE_PROXIMITY_KM_DIVISOR,
    GEOCODING_SCORE_PROXIMITY_MAX,
    GEOCODING_VIEWBOX_DELTA_DEGREES,
    NOMINATIM_BASE_URL,
    NOMINATIM_SEARCH_PATH,
    NOMINATIM_TIMEOUT_S,
    NOMINATIM_USER_AGENT,
)

logger = logging.getLogger(__name__)

_NOMINATIM_SEARCH_URL: str = NOMINATIM_BASE_URL + NOMINATIM_SEARCH_PATH
_NOMINATIM_HEADERS: dict[str, str] = {"User-Agent": NOMINATIM_USER_AGENT}
_EARTH_RADIUS_KM: float = 6371.0

_INSTITUTION_PATTERN: re.Pattern = re.compile(
    r"\b(university|college|campus|institute|school)\b",
    re.IGNORECASE,
)


class GeocodingService:
    """Geocoding and place-lookup using the OpenStreetMap Nominatim API."""

    async def search_places(
        self,
        query: str,
        bias_lat: float | None = None,
        bias_lon: float | None = None,
        limit: int = GEOCODING_DEFAULT_LIMIT,
    ) -> list[dict]:
        """Search for places and return results ranked by relevance.

        Args:
            query:    Place name or address string.
            bias_lat: Optional latitude to bias results toward.
            bias_lon: Optional longitude to bias results toward.
            limit:    Maximum number of results to return.

        Returns:
            List of ``{"label": str, "lat": float, "lng": float}`` dicts,
            ordered by descending relevance score.
        """
        if not query or not query.strip():
            return []

        query = query.strip()
        limit = max(1, min(int(limit), GEOCODING_MAX_LIMIT))
        params = self._build_search_params(
            query, bias_lat, bias_lon, fetch_limit=limit * GEOCODING_FETCH_MULTIPLIER
        )

        try:
            async with httpx.AsyncClient(timeout=NOMINATIM_TIMEOUT_S) as client:
                resp = await client.get(
                    _NOMINATIM_SEARCH_URL, params=params, headers=_NOMINATIM_HEADERS
                )
                resp.raise_for_status()
                raw_results = resp.json()
        except httpx.TimeoutException:
            logger.error("Nominatim request timed out: query=%r", query)
            return []
        except httpx.HTTPStatusError as exc:
            logger.error("Nominatim HTTP error: status=%d query=%r", exc.response.status_code, query)
            return []
        except Exception as exc:
            logger.error("Failed to search places: query=%r error=%s", query, exc)
            return []

        if not isinstance(raw_results, list):
            return []

        scored = self._score_and_rank(raw_results, query, bias_lat, bias_lon)
        results = [candidate for _, candidate in scored[:limit]]
        logger.info(
            "Geocoded query=%r bias=(%s,%s) returned=%d",
            query, bias_lat, bias_lon, len(results),
        )
        return results

    async def search_place_with_osm_meta(
        self,
        query: str,
        bias_lat: float | None = None,
        bias_lon: float | None = None,
    ) -> dict | None:
        """Like :meth:`search_places` but returns the top result with full OSM metadata.

        Tries the query as-is, then strips institution words from a
        comma-separated name (e.g. ``"Benton Hall, Miami University, Ohio"``
        → ``"Benton Hall, Ohio"``) before giving up.

        Returns:
            Dict with keys ``label``, ``lat``, ``lng``, ``osm_id``,
            ``osm_type``, ``extratags``, or ``None`` if nothing was found.
        """
        result = await self._raw_search_with_meta(query, bias_lat, bias_lon)
        if result:
            logger.info("OSM meta search succeeded on first attempt: query=%r", query)
            return result

        simplified = self._strip_institution_segments(query)
        if simplified != query:
            result = await self._raw_search_with_meta(simplified, bias_lat, bias_lon)
            if result:
                logger.info(
                    "OSM meta search succeeded on simplified query: original=%r simplified=%r",
                    query, simplified,
                )
                return result

        logger.warning("OSM meta search found nothing: query=%r", query)
        return None

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    async def _raw_search_with_meta(
        self,
        query: str,
        bias_lat: float | None,
        bias_lon: float | None,
    ) -> dict | None:
        """Fetch the top-scored Nominatim result including OSM metadata fields."""
        params = self._build_search_params(
            query, bias_lat, bias_lon, fetch_limit=5, extratags=True
        )
        try:
            async with httpx.AsyncClient(timeout=NOMINATIM_TIMEOUT_S) as client:
                resp = await client.get(
                    _NOMINATIM_SEARCH_URL, params=params, headers=_NOMINATIM_HEADERS
                )
                resp.raise_for_status()
                raw = resp.json()
        except Exception as exc:
            logger.error("Nominatim raw search failed: query=%r error=%s", query, exc)
            return None

        if not isinstance(raw, list) or not raw:
            return None

        # Score and pick best; keep the original raw item for OSM metadata
        scored_with_raw = self._score_and_rank_with_raw(raw, query, bias_lat, bias_lon)
        if not scored_with_raw:
            return None

        _score, candidate, best_raw = scored_with_raw[0]
        return {
            "label": candidate["label"],
            "lat": candidate["lat"],
            "lng": candidate["lng"],
            "osm_id": int(best_raw.get("osm_id", 0)),
            "osm_type": str(best_raw.get("osm_type", "way")),
            "extratags": best_raw.get("extratags") or {},
        }

    def _score_and_rank(
        self,
        raw_results: list[dict],
        query: str,
        bias_lat: float | None,
        bias_lon: float | None,
    ) -> list[tuple[float, dict]]:
        """Return ``[(score, candidate_dict), ...]`` sorted by descending score."""
        scored: list[tuple[float, dict]] = []
        for item in raw_results:
            if not isinstance(item, dict):
                continue
            try:
                lat = float(item.get("lat", 0))
                lng = float(item.get("lon", 0))
                label = str(item.get("display_name", query))
                score = self._score_candidate(item, query, bias_lat, bias_lon)
                scored.append((score, {"label": label, "lat": lat, "lng": lng}))
            except (TypeError, ValueError):
                continue
        scored.sort(key=lambda x: x[0], reverse=True)
        return scored

    def _score_and_rank_with_raw(
        self,
        raw_results: list[dict],
        query: str,
        bias_lat: float | None,
        bias_lon: float | None,
    ) -> list[tuple[float, dict, dict]]:
        """Return ``[(score, candidate_dict, raw_item), ...]`` sorted by descending score."""
        scored: list[tuple[float, dict, dict]] = []
        for item in raw_results:
            if not isinstance(item, dict):
                continue
            try:
                lat = float(item.get("lat", 0))
                lng = float(item.get("lon", 0))
                label = str(item.get("display_name", query))
                score = self._score_candidate(item, query, bias_lat, bias_lon)
                scored.append((score, {"label": label, "lat": lat, "lng": lng}, item))
            except (TypeError, ValueError):
                continue
        scored.sort(key=lambda x: x[0], reverse=True)
        return scored

    def _score_candidate(
        self,
        candidate: dict,
        query: str,
        bias_lat: float | None,
        bias_lon: float | None,
    ) -> float:
        score = 0.0
        label = str(candidate.get("display_name", "")).lower()
        query_lower = query.lower()

        if query_lower in label:
            score += GEOCODING_SCORE_EXACT_MATCH
        elif any(q in label for q in query_lower.split()):
            score += GEOCODING_SCORE_PARTIAL_MATCH

        if bias_lat is not None and bias_lon is not None:
            try:
                candidate_lat = float(candidate.get("lat", 0))
                candidate_lon = float(candidate.get("lon", 0))
                distance_km = self._haversine_distance(
                    bias_lat, bias_lon, candidate_lat, candidate_lon
                )
                proximity_bonus = max(
                    0.0,
                    GEOCODING_SCORE_PROXIMITY_MAX
                    - (distance_km / GEOCODING_SCORE_PROXIMITY_KM_DIVISOR),
                )
                score += proximity_bonus
            except (TypeError, ValueError):
                pass

        importance = candidate.get("importance", 0)
        if isinstance(importance, (int, float)):
            score += importance * GEOCODING_SCORE_IMPORTANCE_SCALE

        return score

    @staticmethod
    def _haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """Return the great-circle distance in kilometres between two lat/lon points."""
        lon1, lat1, lon2, lat2 = map(radians, [lon1, lat1, lon2, lat2])
        dlon = lon2 - lon1
        dlat = lat2 - lat1
        a = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
        return _EARTH_RADIUS_KM * 2 * asin(sqrt(a))

    @staticmethod
    def _build_search_params(
        query: str,
        bias_lat: float | None,
        bias_lon: float | None,
        fetch_limit: int,
        extratags: bool = False,
    ) -> dict:
        params: dict = {"q": query, "format": "json", "limit": fetch_limit}
        if bias_lat is not None and bias_lon is not None:
            delta = GEOCODING_VIEWBOX_DELTA_DEGREES
            params["viewbox"] = (
                f"{bias_lon - delta},{bias_lat - delta},"
                f"{bias_lon + delta},{bias_lat + delta}"
            )
            params["bounded"] = "0"
        if extratags:
            params["extratags"] = 1
        return params

    @staticmethod
    def _strip_institution_segments(query: str) -> str:
        """Remove institution-name segments from a comma-separated query string."""
        parts = [p.strip() for p in query.split(",")]
        if len(parts) <= 1:
            return query
        filtered = [parts[0]] + [
            p for p in parts[1:] if not _INSTITUTION_PATTERN.search(p.strip())
        ]
        return ", ".join(filtered)
