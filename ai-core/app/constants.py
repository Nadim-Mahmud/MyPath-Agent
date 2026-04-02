"""Application-wide string and numeric constants.

All hard-coded strings and configuration literals live here.
Import from this module rather than embedding literals elsewhere.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# External API base URLs
# ---------------------------------------------------------------------------

NOMINATIM_BASE_URL: str = "https://nominatim.openstreetmap.org"
NOMINATIM_SEARCH_PATH: str = "/search"
NOMINATIM_REVERSE_PATH: str = "/reverse"
OVERPASS_BASE_URL: str = "https://overpass-api.de/api/interpreter"

# ---------------------------------------------------------------------------
# HTTP client settings (seconds)
# ---------------------------------------------------------------------------

NOMINATIM_TIMEOUT_S: int = 20
OVERPASS_TIMEOUT_S: int = 25
ROUTING_TIMEOUT_S: int = 30
REVERSE_GEOCODE_TIMEOUT_S: int = 10
LLM_TIMEOUT_S: int = 60

# ---------------------------------------------------------------------------
# HTTP headers
# ---------------------------------------------------------------------------

NOMINATIM_USER_AGENT: str = "Wheelway/1.0 (wheelchair-navigation-ai)"

# ---------------------------------------------------------------------------
# Geocoding / proximity scoring
# ---------------------------------------------------------------------------

GEOCODING_VIEWBOX_DELTA_DEGREES: float = 0.45  # ~50 km soft viewbox half-width
GEOCODING_SCORE_EXACT_MATCH: float = 100.0
GEOCODING_SCORE_PARTIAL_MATCH: float = 50.0
GEOCODING_SCORE_PROXIMITY_MAX: float = 50.0
GEOCODING_SCORE_PROXIMITY_KM_DIVISOR: float = 2.0  # km per proximity point
GEOCODING_SCORE_IMPORTANCE_SCALE: float = 10.0
GEOCODING_DEFAULT_LIMIT: int = 5
GEOCODING_MAX_LIMIT: int = 10
GEOCODING_FETCH_MULTIPLIER: int = 2  # over-fetch before scoring/filtering

# ---------------------------------------------------------------------------
# Overpass query settings
# ---------------------------------------------------------------------------

OVERPASS_ENTRANCE_RADIUS_M: int = 60
OVERPASS_MEMBER_QUERY_TIMEOUT_S: int = 20
OVERPASS_RADIUS_QUERY_TIMEOUT_S: int = 15

# ---------------------------------------------------------------------------
# Wheelchair accessibility labels  (OSM tag value → human-readable string)
# ---------------------------------------------------------------------------

WHEELCHAIR_LABEL_YES: str = "fully wheelchair accessible"
WHEELCHAIR_LABEL_NO: str = "not wheelchair accessible"
WHEELCHAIR_LABEL_LIMITED: str = "limited wheelchair accessibility"
WHEELCHAIR_LABEL_NOT_SPECIFIED: str = "not specified in OSM"

# Substring used to detect "fully accessible" from a stored wheelchair label
WHEELCHAIR_FULLY_ACCESSIBLE_MARKER: str = "fully"

# ---------------------------------------------------------------------------
# MCP tool names
# ---------------------------------------------------------------------------

TOOL_GET_ROUTE: str = "get_route"
TOOL_GEOCODE_PLACE: str = "geocode_place"
TOOL_GET_PLACE_ACCESSIBILITY: str = "get_place_accessibility"
TOOL_GET_OBSTACLES: str = "get_obstacles"
TOOL_REPORT_OBSTACLE: str = "report_obstacle"

# ---------------------------------------------------------------------------
# User intent identifiers
# ---------------------------------------------------------------------------

INTENT_ROUTE: str = "route"
INTENT_ACCESSIBILITY: str = "accessibility"
INTENT_GENERAL: str = "general"

# ---------------------------------------------------------------------------
# Chat context / message markers
# ---------------------------------------------------------------------------

CONTEXT_BLOCK_MARKER: str = "\n\n[Context]"
PRE_RESOLVED_MARKER: str = "\n\n[Pre-resolved] "
ROUTE_FOUND_MARKER_PREFIX: str = "[Route found]"

# ---------------------------------------------------------------------------
# Negative / failure message detection keywords
# ---------------------------------------------------------------------------

NEGATIVE_MESSAGE_FAILURE_KEYWORDS: tuple[str, ...] = (
    "locate",
    "location",
    "find",
    "address",
    "place",
    "geocod",
    "route",
    "direct",
)

NEGATIVE_MESSAGE_PHRASES: tuple[str, ...] = (
    "unable",
    "sorry",
    "cannot",
    "can't",
    "failed",
    "unavailable",
    "regret",
    "couldn't",
    "trouble",
    "apologize",
    "having trouble",
)

# Phrases that indicate the model produced an apologetic/failure response
# despite successfully computing a route
APOLOGETIC_PHRASES: tuple[str, ...] = (
    "unable",
    "sorry",
    "cannot",
    "can't",
    "unfortunately",
    "regret",
    "unavailable",
)

# ---------------------------------------------------------------------------
# Response message templates
# ---------------------------------------------------------------------------

ROUTE_SUCCESS_MESSAGE_TEMPLATE: str = (
    "I found an accessible route to **{destination}**. "
    "I've loaded it on the map for you. Check it out!"
)

ROUTE_FALLBACK_MESSAGE_TEMPLATE: str = (
    "I found an accessible route from your current location to **{destination}**. "
    "Estimated distance: **{distance} mi**, travel time: **{eta} min**. "
    "I've loaded it on the map for you."
)

ROUTE_NOTE_TEMPLATE: str = (
    "{prefix} A wheelchair-accessible route was successfully generated to "
    "{destination} (lat={lat}, lng={lng}). "
    "The route is loaded on the map. No need to call any routing tools again for this request."
)

ROUTE_DESTINATION_FALLBACK_LABEL: str = "your destination"
MY_LOCATION_LABEL: str = "My Location"

# ---------------------------------------------------------------------------
# CORS
# ---------------------------------------------------------------------------

CORS_ALLOWED_ORIGINS: list[str] = [
    "http://localhost:3000",
    "http://localhost:5173",
]

CORS_ALLOWED_METHODS: list[str] = ["GET", "POST", "DELETE", "OPTIONS"]

# ---------------------------------------------------------------------------
# FastAPI application metadata
# ---------------------------------------------------------------------------

APP_TITLE: str = "Wheelway AI Core"
APP_SERVICE_NAME: str = "wheelway-ai-core"

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

LOG_FORMAT: str = "%(asctime)s %(levelname)s [%(name)s] %(message)s"
