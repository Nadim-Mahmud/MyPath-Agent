# API Reference

Complete reference for all HTTP APIs exposed by the MyPathAgent services.

---

## Routing Server — port 8080

Base URL (local): `http://localhost:8080`

### Authentication

All `/route/*` endpoints require:

```
Authorization: Bearer <api-key>
```

The default development API key is `0aed6a955c59dc3c75dba711c6b74edb`, configured in `routing-server/src/main/resources/application.properties`.

Requests without a valid key return `401 Unauthorized`.

---

### GET /

Health check.

**Auth:** None

**Response `200`:**

```
Hi there..
```

---

### GET /route/getSingleRoute

Generate a wheelchair-accessible route between two geographic points.

**Auth:** Bearer token required

**Query Parameters:**

| Parameter | Type | Required | Description |
|---|---|---|---|
| `srcLat` | double | Yes | Origin latitude |
| `srcLon` | double | Yes | Origin longitude |
| `destLat` | double | Yes | Destination latitude |
| `destLon` | double | Yes | Destination longitude |

**Example request:**

```bash
curl -H "Authorization: Bearer 0aed6a955c59dc3c75dba711c6b74edb" \
  "http://localhost:8080/route/getSingleRoute?srcLat=39.507&srcLon=-84.745&destLat=39.513&destLon=-84.738"
```

**Response `200`:**

```json
{
  "routes": {
    "points": [
      {
        "start_location": {
          "latitude": 39.507,
          "longitude": -84.745,
          "elevation": 285.2
        },
        "end_location": {
          "latitude": 39.508,
          "longitude": -84.744,
          "elevation": 284.8
        },
        "points": [
          { "latitude": 39.507, "longitude": -84.745, "elevation": 285.2 },
          { "latitude": 39.508, "longitude": -84.744, "elevation": 284.8 }
        ],
        "surface": "asphalt",
        "distance": {
          "value": 148.0,
          "type": "feet",
          "text": "0.03 mi"
        },
        "duration": {
          "value": 21.0,
          "type": "second",
          "text": "0.35 min"
        },
        "maneuver": "Turn right",
        "travel_mode": null,
        "instructions": null,
        "incline": 1.4
      }
    ]
  }
}
```

**Route point fields:**

| Field | Type | Description |
|---|---|---|
| `start_location` | Coordinate | Start of this segment |
| `end_location` | Coordinate | End of this segment |
| `points` | Coordinate[] | Full polyline for this segment |
| `surface` | string | Surface type: `asphalt`, `concrete`, `paving_stones`, `sett`, `unpaved`, `gravel`, `dirt`, `unknown` |
| `distance.value` | number | Distance in feet |
| `distance.text` | string | Human-readable distance |
| `duration.value` | number | Duration in seconds |
| `duration.text` | string | Human-readable duration |
| `maneuver` | string | Navigation instruction |
| `incline` | number | Grade percentage (positive = uphill, negative = downhill) |

**Maneuver values:**

| Value |
|---|
| `Go straight` |
| `Turn left` |
| `Turn slightly left` |
| `Make a steep left turn` |
| `Turn right` |
| `Turn slightly right` |
| `Make a steep right turn` |
| `Reached` |

**Error responses:**

| Code | Description |
|---|---|
| `401` | Missing or invalid Authorization header |
| `404` | No accessible route found between the given coordinates |
| `500` | Internal server error |

---

## AI Core — port 8000

Base URL (local): `http://localhost:8000`

No authentication required on the AI Core in the current development setup. In production, access is restricted to the internal Docker network.

---

### GET /health

Liveness check.

**Response `200`:**

```json
{
  "status": "ok",
  "service": "mypathagent-ai-core"
}
```

---

### POST /chat

Process a natural-language message and return an AI response, optionally with a route action or map pins.

**Request body:**

```json
{
  "session_id": "550e8400-e29b-41d4-a716-446655440000",
  "message": "Take me to the nearest coffee shop",
  "context": {
    "user_location": { "lat": 39.507, "lng": -84.745 },
    "map_center":    { "lat": 39.510, "lng": -84.740 },
    "active_route":  null
  }
}
```

**Request fields:**

| Field | Type | Required | Description |
|---|---|---|---|
| `session_id` | string | Yes | Unique session identifier (UUID recommended) |
| `message` | string | Yes | User message, max 500 characters |
| `context` | object | No | Map and location context |
| `context.user_location` | `{lat, lng}` | No | User's GPS coordinates |
| `context.map_center` | `{lat, lng}` | No | Current map viewport centre |
| `context.active_route` | Route object | No | Full route currently displayed on the map |

**Response `200`:**

```json
{
  "session_id": "550e8400-e29b-41d4-a716-446655440000",
  "message": "I found a route to Kofenya Coffee (0.2 miles, ~3 min). The path is mostly asphalt.",
  "route_action": {
    "origin":      { "lat": 39.507, "lng": -84.745, "label": "My Location" },
    "destination": { "lat": 39.509, "lng": -84.744, "label": "Kofenya Coffee" }
  },
  "map_pins": null,
  "response_intent": "route"
}
```

**Response fields:**

| Field | Type | Description |
|---|---|---|
| `session_id` | string | Echoed from request |
| `message` | string | AI response text (may contain Markdown) |
| `route_action` | object \| null | If set, the frontend should fetch and render this route |
| `route_action.origin` | `{lat, lng, label?}` | Route start point |
| `route_action.destination` | `{lat, lng, label?}` | Route end point |
| `map_pins` | MapPin[] \| null | Accessibility pins to render on the map |
| `response_intent` | string | `route` \| `accessibility` \| `general` |

**MapPin object:**

| Field | Type | Description |
|---|---|---|
| `lat` | number | Pin latitude |
| `lng` | number | Pin longitude |
| `label` | string | Tooltip text (e.g. "Accessible entrance (automatic door)") |
| `pin_type` | string | `accessible` \| `ramp` |

**Accessibility query example response:**

```json
{
  "session_id": "550e8400-e29b-41d4-a716-446655440000",
  "message": "Upham Hall has a fully accessible entrance on the north side with an automatic door and a ramp.",
  "route_action": null,
  "map_pins": [
    {
      "lat": 39.5092,
      "lng": -84.7374,
      "label": "Accessible entrance (automatic door) · ramp",
      "pin_type": "accessible"
    },
    {
      "lat": 39.5091,
      "lng": -84.7375,
      "label": "Wheelchair ramp",
      "pin_type": "ramp"
    }
  ],
  "response_intent": "accessibility"
}
```

**Error responses:**

| Code | Description |
|---|---|
| `422` | Request body failed validation |
| `503` | Gemini API unavailable |
| `500` | Unexpected server error |

---

### DELETE /session/{session_id}

Clear the conversation history for a session.

**Path parameter:** `session_id` — the session to clear

**Response `200`:**

```json
{
  "status": "cleared",
  "session_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

---

### POST /geocode

Search for places by name, with optional coordinate bias for local results.

**Request body:**

```json
{
  "query": "CVS Pharmacy Oxford Ohio",
  "bias_lat": 39.507,
  "bias_lon": -84.745,
  "limit": 5
}
```

**Request fields:**

| Field | Type | Required | Default | Description |
|---|---|---|---|---|
| `query` | string | Yes | — | Place name or address |
| `bias_lat` | number | No | null | Latitude to bias results toward |
| `bias_lon` | number | No | null | Longitude to bias results toward |
| `limit` | integer | No | 5 | Maximum results to return |

**Response `200`:**

```json
{
  "query": "CVS Pharmacy Oxford Ohio",
  "results": [
    {
      "label": "CVS Pharmacy, High Street, Oxford, Butler County, Ohio, United States",
      "lat": 39.5089,
      "lng": -84.7451
    }
  ]
}
```

**Notes:**
- Powered by OpenStreetMap Nominatim. Results may vary with specificity of the query.
- Returns an empty `results` array (not an error) when no places are found.
- Adding city and state to the query significantly improves result quality.

---

## Frontend Proxy

In production, the frontend nginx serves the app and proxies API calls:

| Path | Proxied to |
|---|---|
| `/route/*` | `http://routing-server:8080` |
| `/geocode` | `http://ai-core:8000` |
| `/chat` | `http://ai-core:8000` |
| `/session/*` | `http://ai-core:8000` |

In development, the frontend Vite dev server uses the same proxy configuration via `vite.config.ts`.

---

## Planned Endpoints (not yet implemented)

### Routing Server

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/v1/obstacles` | List known accessibility obstacles near a location |
| `POST` | `/api/v1/obstacles` | Report a new obstacle |
| `PATCH` | `/api/v1/obstacles/{id}/verify` | Verify a reported obstacle |
| `POST` | `/api/v1/chat` | Proxy chat to AI core |
| `GET` | `/api/v1/chat/stream` | Stream chat response via SSE |
| `DELETE` | `/api/v1/chat/{sessionId}` | Clear a chat session |
| `POST` | `/api/v1/auth/login` | JWT login |
| `POST` | `/api/v1/auth/signup` | JWT signup |
| `GET` | `/api/v1/routes/{id}` | Retrieve saved route |
| `POST` | `/api/v1/routes/{id}/feedback` | Submit route feedback |
