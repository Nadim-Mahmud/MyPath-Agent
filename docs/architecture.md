# Architecture

## Overview

Wheelway is a three-tier system where each service has a single clear responsibility:

```
Browser (React App) :3000
        |
        |  REST (route fetch, geocoding)
        |  REST (AI chat — direct in dev)
        v
AI Core (FastAPI + MCP) :8000
        |
        |  HTTP — tool calls
        v
Routing Server (Spring Boot + GraphHopper) :8080
        |
        v
    OSM / Geofabrik data
    Overpass API (accessibility queries)
    Nominatim (geocoding)
```

> **Note:** In the target architecture, the frontend calls the routing server which proxies AI chat to the AI core. During development, the frontend calls the AI core directly at port 8000 because the routing server chat proxy is not yet implemented.

---

## Components

### Frontend (React 19 + TypeScript + Vite)

The single-page application (SPA) that users interact with. It renders a full-screen Leaflet map, handles route search, displays turn-by-turn directions, and hosts the AI chat interface. The frontend never does routing computation — it consumes the routing server API and the AI core chat API.

### Routing Server (Java 17 + Spring Boot + GraphHopper)

The backbone of the system. It maintains a cached GraphHopper routing graph built from OpenStreetMap data and serves wheelchair-accessible routes as a REST API. A custom wheelchair routing profile weights surface types, penalises inclines, and avoids stairs. The graph is refreshed automatically every night from fresh OSM data.

### AI Core (Python 3.11 + FastAPI + Gemini)

A standalone microservice providing a conversational AI assistant for accessibility-specific navigation. It manages per-session conversation history, enriches user messages with GPS context and route state, detects intent (route planning vs. accessibility information), and runs an agentic LLM loop via an in-process MCP server.

---

## Data Flow: Route Search

```
User types origin + destination
        |
SearchBar.tsx debounce (300ms)
        |
POST /geocode (AI Core)
        |── Nominatim search with optional bias coordinates
        v
Autocomplete suggestions rendered
        |
User selects both origin and destination
        |
routingService.ts
        |
GET /route/getSingleRoute (Routing Server)
  ?srcLat=...&srcLon=...&destLat=...&destLon=...
  Authorization: Bearer <key>
        |
GraphHopper wheelchair profile computes route
        |
RouteResponse JSON
        |
MapCanvas.tsx renders polylines (color-coded by surface)
RoutePanel.tsx renders turn-by-turn steps
```

---

## Data Flow: AI Chat Request

```
User types message in ChatPanel
        |
chatService.ts
        |
POST /chat (AI Core)
  { session_id, message, context: { user_location, map_center, active_route } }
        |
ChatService.chat()
  1. Load session history
  2. Detect intent (route / accessibility / general)
  3. Fast-path: if route intent + GPS, try resolving directly without LLM
  4. Enrich message with GPS context and intent hints
  5. Call GeminiProvider.complete()
        |
GeminiProvider agentic loop:
  - POST to Gemini generateContent API
  - Model may call MCP tools:
      get_route → GET /route/getSingleRoute (Routing Server)
      geocode_place → Nominatim search
      get_place_accessibility → Nominatim + Overpass API
      get_obstacles → (planned) routing server
      report_obstacle → (planned) routing server
  - Loop repeats until no more tool calls
        |
ChatResponse returned:
  { session_id, message, route_action?, map_pins?, response_intent }
        |
Frontend handles response:
  - Displays message in chat
  - If route_action: auto-populates origin/destination, fetches route, renders on map
  - If map_pins: renders accessibility pins (♿ ramp icons)
```

---

## MCP (Model Context Protocol) Architecture

The AI core runs an in-process MCP server — not a separate service. The MCP server is a tool registry that exposes typed function declarations to the Gemini LLM. The LLM autonomously decides when to call tools based on the user's message.

```
GeminiProvider
    |
    ├── Sends tool_declarations to Gemini API
    |   (get_route, geocode_place, get_place_accessibility, ...)
    |
    ├── Gemini returns functionCall parts
    |
    └── MCPServer.execute_tool(name, args)
            |
            ├── GetRoute.execute() → HTTP → Routing Server :8080
            ├── GeocodePlace.execute() → HTTP → Nominatim
            ├── GetPlaceAccessibility.execute() → Nominatim + Overpass
            ├── GetObstacles.execute() → (planned)
            └── ReportObstacle.execute() → (planned)
```

---

## Intent Classification

Every chat message is classified before reaching the LLM:

| Intent | Trigger phrases | AI behaviour |
|---|---|---|
| `route` | "take me to", "route to", "directions to", "navigate to" | Prioritise routing; populate map |
| `accessibility` | "accessible", "ramp", "elevator", "wheelchair", "entrance" | Return accessibility details; don't overwrite route |
| `general` | Everything else | Answer directly; only route when explicitly asked |

Intent classification enables:
- **Fast-path routing** — common route requests resolved without an LLM call at all
- **Route/accessibility separation** — accessibility queries don't accidentally clear an active route
- **Context enrichment** — the LLM prompt includes intent-specific instructions

---

## Surface Colour Coding

The map uses colour to communicate surface quality at a glance:

| Surface type | Colour | Hex |
|---|---|---|
| Asphalt, concrete | Blue | `#1A56DB` |
| Paving stones, sett | Amber | `#f59e0b` |
| Unpaved, gravel, dirt | Red | `#ef4444` |
| Unknown | Gray | `#6b7280` |

---

## Deployment

### Development

```
make dev
```

All three services start with hot-reload:
- Frontend: Vite dev server, source bind-mounted
- AI Core: uvicorn with `--reload`, source bind-mounted
- Routing Server: pre-built JAR, graph cache pre-loaded (~30s startup)

### Production

```
make prod
```

- Frontend: nginx serves the compiled Vite bundle
- AI Core: uvicorn without reload
- Routing Server: same JAR

### Docker Compose Services

| Service | Container | Network alias |
|---|---|---|
| Frontend | `frontend` | `frontend` |
| Routing Server | `routing-server` | `routing-server` |
| AI Core | `ai-core` | `ai-core` |

All services communicate on the `wheelway` Docker network. The frontend is the only service exposed to the host on port 3000.
