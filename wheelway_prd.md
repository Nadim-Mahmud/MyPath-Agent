# Wheelway — Product Requirements Document

### Wheelchair-Accessible Navigation Platform

|                  |              |                     |               |
| ---------------- | ------------ | ------------------- | ------------- |
| **Product Name** | Wheelway     | **Version**         | 1.0           |
| **Status**       | In Progress  | **Date**            | April 1, 2025 |
| **Author**       | Product Team | **Confidentiality** | Internal      |

> _Every path, accessible._

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Problem Statement](#2-problem-statement)
3. [Goals & Success Metrics](#3-goals--success-metrics)
4. [Stakeholders & Users](#4-stakeholders--users)
5. [System Architecture](#5-system-architecture)
6. [Frontend Requirements](#6-frontend-requirements-react-web-app)
7. [routing server Requirements](#7-routing server-requirements-spring-boot)
8. [AI Core Requirements](#8-ai-core-requirements-python-fastapi)
9. [User Stories](#9-user-stories)
10. [Non-Functional Requirements](#10-non-functional-requirements)
11. [Repository Structure](#11-repository-structure)
12. [Milestones & Delivery Phases](#12-milestones--delivery-phases)
13. [Risks & Mitigations](#13-risks--mitigations)
14. [Open Questions](#14-open-questions)
15. [Glossary](#15-glossary)

---

## 1. Executive Summary

Wheelway is a wheelchair-accessible navigation platform that empowers wheelchair users to independently plan, discover, and navigate routes in the real world. Unlike general-purpose mapping solutions, Wheelway treats accessibility as a first-class concern — every route, every turn, and every recommendation is filtered through the lens of wheelchair usability.

The platform consists of three tightly integrated components:

- A **React web application** delivering a Google Maps-like navigation experience optimized for accessibility routing
- An existing **Java Spring Boot routing server** that generates wheelchair-accessible routes via a proprietary routing engine
- A **Python-based AI core service** that powers a conversational chat assistant for natural-language navigation guidance

Together, these components deliver an experience where a wheelchair user can open Wheelway, type or speak a destination, and receive a fully accessible route with step-by-step guidance — all backed by an AI assistant that understands their specific accessibility needs.

---

## 2. Problem Statement

### 2.1 The Accessibility Gap in Navigation

Existing navigation solutions such as Google Maps, Apple Maps, and Waze are built primarily for able-bodied pedestrians and drivers. While some offer limited accessibility filters, they consistently fall short for wheelchair users:

- Route recommendations include stairs, steep inclines, and uneven terrain without warning
- No real-time context about ramp availability, elevator status, or surface conditions
- No natural language interface for accessibility-specific queries such as _"find me a route that avoids cobblestones"_
- No feedback loop for users to report inaccessible infrastructure

### 2.2 Who Is Affected

In the United States alone, approximately **3.3 million people** use wheelchairs. Globally, the World Health Organization estimates over **75 million people** require a wheelchair. These users face daily navigation challenges that Wheelway is designed to solve.

### 2.3 Opportunity

By combining a purpose-built accessible routing engine with a modern map UI and an AI conversational assistant, Wheelway creates a uniquely differentiated product in an underserved market. The opportunity exists not only as a consumer product but also as infrastructure for smart cities, healthcare providers, and venue operators.

---

## 3. Goals & Success Metrics

### 3.1 Product Goals

- Deliver a map-based navigation UI that surfaces only wheelchair-accessible routes
- Provide turn-by-turn navigation that accounts for ramps, curb cuts, and surface types
- Offer a conversational AI assistant that can answer accessibility-specific navigation questions
- Establish a foundation that can scale to mobile applications and additional cities

### 3.2 Success Metrics

| Metric                       | Target                                             | Measurement Method        |
| ---------------------------- | -------------------------------------------------- | ------------------------- |
| Route Accessibility Accuracy | > 95% of generated routes are wheelchair-navigable | User feedback + audit     |
| UI Time-to-Route             | < 10 seconds from search to displayed route        | Frontend performance logs |
| AI Chat Response Time        | < 3 seconds for first token                        | AI core latency logs      |
| Chat Resolution Rate         | > 80% of queries answered without escalation       | Session analytics         |
| User Satisfaction (CSAT)     | > 4.2 / 5.0                                        | In-app rating prompt      |
| Accessibility Compliance     | WCAG 2.1 AA                                        | Automated + manual audit  |

---

## 4. Stakeholders & Users

### 4.1 Primary Users

| User Type                  | Description                                                                         |
| -------------------------- | ----------------------------------------------------------------------------------- |
| **Wheelchair User**        | Primary end user. Needs reliable, safe, accessible routes from point A to B.        |
| **Caregiver / Companion**  | Plans routes on behalf of a wheelchair user. May have different device and context. |
| **Accessibility Advocate** | Tests and reports route data quality. Power user of feedback features.              |

### 4.2 Internal Stakeholders

| Stakeholder                | Interest                                                      |
| -------------------------- | ------------------------------------------------------------- |
| Product Team               | Feature prioritization, roadmap, user research                |
| routing server Engineering | Spring Boot routing API maintenance and enhancement           |
| Frontend Engineering       | React UI development and performance                          |
| AI Engineering             | AI core development, prompt engineering, LLM integration      |
| QA Team                    | Accessibility testing, regression, and performance validation |

---

## 5. System Architecture

### 5.1 High-Level Overview

Wheelway is a three-tier system. The frontend (React) communicates exclusively with the routing server (Spring Boot). The routing server acts as the orchestration layer — it handles authentication, caching, and routes calls to both the routing engine and the AI core service. **The frontend never calls the AI core directly**, ensuring security and rate-limiting are centralized.

The AI core embeds an MCP (Model Context Protocol) server that exposes routing and obstacle tools to the LLM. When the LLM needs route data or system information, it calls these MCP tools — which in turn call the Spring Boot routing server via HTTP.

```
Browser (React App) :5173
        |  REST / WebSocket
        v
Spring Boot routing server :8080
   |              |
   v              v
PostgreSQL     AI Core (FastAPI + MCP Server) :8000
(PostGIS)           |
                    ├── MCP tools → HTTP → Spring Boot :8080
                    v
              LLM API (OpenAI / Claude)
```

### 5.2 Component Summary

| Component      | Technology                                                            | Port |
| -------------- | --------------------------------------------------------------------- | ---- |
| Frontend       | React 19, TypeScript, Vite, Leaflet / Mapbox                          | 5173 |
| Routing Server | Java 17, Spring Boot 3.4.3, Spring Security, GraphHopper              | 8080 |
| AI Core + MCP  | Python 3.11, FastAPI, Google Gemini 2.0 Flash, MCP tools (in-process) | 8000 |
| Database       | PostgreSQL 16 + PostGIS extension                                     | 5432 |

---

## 6. Frontend Requirements (React Web App)

### 6.1 Overview

The Wheelway frontend delivers a Google Maps-style interactive map experience purpose-built for wheelchair-accessible navigation. It is a single-page application (SPA) built with React and TypeScript, communicating with the Spring Boot routing server via REST and WebSocket.

---

### 6.2 Core Map Features

#### FR-01: Interactive Map Canvas

- Render a full-screen interactive map using Leaflet.js (OpenStreetMap tiles)
- Support pan, zoom, and click interactions
- Display the user's current location with a distinct wheelchair-friendly marker
- Map must be keyboard-navigable and screen-reader compatible (WCAG 2.1 AA)
- **Locate Me button** — a crosshair/GPS icon button overlaid on the map (bottom-right, above zoom controls) that, when clicked, uses the browser Geolocation API to pan and zoom the map to the user's current position; shows a spinner while acquiring location and a dismissible error toast if geolocation fails or is denied

#### FR-02: Point-to-Point Route Search

- Search bar accepts a free-text origin and destination
- Autocomplete suggestions sourced from a geocoding API (e.g. Nominatim or Mapbox)
- On submission, call routing server routing API and render the accessible route as a polyline on the map
- Display route summary: total distance, estimated travel time, number of ramps, elevation gain

#### FR-03: Route Display & Visualization

- Render the route polyline in Wheelway brand blue (`#1A56DB`) with 4px stroke
- Mark key accessibility waypoints: ramp locations, curb cuts, accessible crossings
- Highlight inaccessible segments (if a fallback route is used) in amber with a warning tooltip
- Show start and end pins with clear A/B labels

#### FR-04: Turn-by-Turn Navigation Panel

- Side panel listing each navigation step with icon, instruction text, and distance
- Icons differentiate: straight, turn left, turn right, ramp up, ramp down, elevator
- Active step highlighted as user progresses (GPS-based or manual progression)
- "Recalculate Route" button available at all times

---

### 6.3 AI Chat Widget

#### FR-05: Floating Chat Button

- A persistent floating action button (FAB) in the bottom-right corner of the map
- Wheelchair icon with _"Ask Cccessible AI"_ tooltip on hover
- Opens the chat panel as a slide-up drawer on mobile, side panel on desktop

#### FR-06: Chat Panel UI

- Message thread showing user messages (right-aligned) and AI responses (left-aligned)
- AI messages support markdown rendering: bold, lists, hyperlinks
- Typing indicator (three-dot animation) while AI response streams in
- Streaming response rendering via SSE — text appears word-by-word, not all at once
- Chat history persists within the browser session; cleared on page reload

#### FR-07: Chat Input

- Text input field with placeholder: _"Ask about accessible routes, ramps, elevators..."_
- Send on Enter key or click of Send button
- Voice input button using browser speech-to-text: user can tap mic, speak a prompt, and the recognized text is sent through the same AI chat pipeline
- Input disabled while AI is generating a response (spinner shown)
- Character limit: 500 characters with live counter

#### FR-08: Map–Chat Integration

- If the user asks for a route using place names (e.g., "from X to Y"), AI must geocode both places, fetch an accessible route, and automatically render it on the map
- The app must auto-populate origin and destination fields from AI-resolved locations and trigger routing without requiring a separate "Show on Map" click
- Chat context is passed to the AI: current map center, active route (if any), user location
- If a route is successfully computed and rendered, the chat message must be positive and confirm the route is ready, regardless of intermediate failures or Gemini response quirks
- The backend automatically tries multiple geocoding candidates to handle full addresses (e.g., "Roberts Apartments at 211 North Beech Street") and returns the first successful match
- For route accessibility-status questions, AI receives a compact route summary only (per segment: `surface`, `distance`, `duration`, `maneuver`, `incline`) and excludes start/end coordinates and route polyline point lists to reduce token usage
- AI inference uses a short rolling history window and prioritizes the latest user query; stale context blocks from older turns are stripped before model calls to reduce history interference
- If no route is currently rendered on the map, chat context must explicitly state "no active route" and instruct the AI to ignore earlier turns that imply a route is still active
- Chat pipeline must classify each prompt intent as route-planning vs accessibility-information and react accordingly: route intents update origin/destination and route polyline, while accessibility intents prioritize map accessibility pins/details and must not overwrite route state unless the user explicitly asks to navigate
- **Retry Recovery Strategy**: When a user provides more specific location details after a previous failed geocoding attempt (e.g., retrying with full address "McVey Data Science Building at 105 Tallawanda Rd"), the system:
  - Detects the retry via history analysis (identifies prior negative geocoding message + current location request)
  - Strips the previous failed geocoding message from chat history to prevent negative anchoring
  - Uses increased geocoding candidate limit (10 instead of 5) for full addresses (detected by presence of number + street keywords)
  - Never assumes prior inability to find a location precludes success with more specific details
  - Instructs the model: "Previously failed lookups do not preclude success with a more specific address"

---

### 6.4 Additional UI Features

| Feature | Description |
| ------- | ----------- |

| **FR-10: Route Preferences** | Settings panel to configure: max incline percentage, prefer indoor routes, avoid cobblestones, prefer covered routes. |
| **FR-12: Dark Mode** | Full dark mode toggle. Map tiles switch to a dark theme. Respects OS-level preference. |
| **FR-13: Responsive Design** | Fully usable on mobile (375px+), tablet, and desktop. Navigation panel collapses to bottom sheet on mobile. |

---

## 7. routing server Requirements (Spring Boot)

### 7.1 Overview

The existing Java Spring Boot application serves as the system's backbone. It exposes REST APIs consumed by the frontend and orchestrates calls to the AI core service. The routing server owns data persistence, authentication, and business logic.

### 7.2 Implemented API Endpoints

> **Note:** The routing server is currently in early development. Only the core routing endpoint is implemented. Planned endpoints (obstacles, chat proxy, auth) are not yet built.

#### Base

| Method + Path | Description                                    | Auth Required |
| ------------- | ---------------------------------------------- | ------------- |
| `GET /`       | Health/liveness check — returns `"Hi there.."` | No            |

#### Routing API _(implemented)_

| Method + Path               | Description                                               | Auth Required        |
| --------------------------- | --------------------------------------------------------- | -------------------- |
| `GET /route/getSingleRoute` | Generate a wheelchair-accessible route between two points | Yes — Bearer API key |

**Query Parameters for `GET /route/getSingleRoute`:**

| Parameter | Type   | Required | Description           |
| --------- | ------ | -------- | --------------------- |
| `srcLat`  | double | Yes      | Origin latitude       |
| `srcLon`  | double | Yes      | Origin longitude      |
| `destLat` | double | Yes      | Destination latitude  |
| `destLon` | double | Yes      | Destination longitude |

**Authentication:** All `/route/*` endpoints require an `Authorization: Bearer <api-key>` header. Requests without a valid key return HTTP 401.

**Response Schema (`GET /route/getSingleRoute`):**

```json
{
  "routes": {
    "points": [
      {
        "start_location": {
          "latitude": 0.0,
          "longitude": 0.0,
          "elevation": 0.0
        },
        "end_location": { "latitude": 0.0, "longitude": 0.0, "elevation": 0.0 },
        "points": [{ "latitude": 0.0, "longitude": 0.0, "elevation": 0.0 }],
        "surface": "asphalt",
        "distance": { "value": 123.45, "type": "feet", "text": "0.02 mi" },
        "duration": { "value": 30.5, "type": "second", "text": "0.51 min" },
        "maneuver": "turn-left | turn-right | straight | end",
        "travel_mode": null,
        "instructions": null,
        "incline": 2.3
      }
    ]
  }
}
```

Each element in `points` represents one route segment, grouped by surface type and split at maneuver points. Segments include incline percentage, distance, duration, and the next maneuver direction.

**Error Responses:**

| HTTP Status | Condition                                                       |
| ----------- | --------------------------------------------------------------- |
| 401         | Missing or invalid `Authorization` header / API key             |
| 404         | No route found between the given coordinates                    |
| 500         | Internal server error (includes `timestamp`, `message`, `path`) |

#### Planned APIs _(not yet implemented)_

| API Area           | Planned Endpoints                                                                        |
| ------------------ | ---------------------------------------------------------------------------------------- |
| Obstacle reporting | `GET /api/v1/obstacles`, `POST /api/v1/obstacles`, `PATCH /api/v1/obstacles/{id}/verify` |
| AI Chat proxy      | `POST /api/v1/chat`, `GET /api/v1/chat/stream`, `DELETE /api/v1/chat/{sessionId}`        |
| Auth               | JWT login/signup, Google OAuth 2.0                                                       |
| Route history      | `GET /api/v1/routes/{id}`, `POST /api/v1/routes/{id}/feedback`                           |

### 7.3 Non-Functional routing server Requirements

- All endpoints must respond within **500ms** (excluding AI chat stream)
- Authentication: API key via `Authorization: Bearer` header (currently implemented); JWT + Google OAuth 2.0 planned
- Rate limiting: 100 requests/min per IP for routing API, 20 requests/min for chat API _(planned)_
- CORS configured to accept requests only from known frontend origins
- Database: PostgreSQL with PostGIS for geospatial route storage and obstacle indexing _(planned; not yet wired up)_
- Logging: Structured JSON logs (SLF4J + Logback); log file written to `mypath_stdout.log`
- Map data: GraphHopper routing engine with a custom wheelchair profile; OSM data cached in `myPathDataStore/routing-graph-cache/`; map cache refreshed via a scheduled `MapUpdateScheduler` cron job

---

## 8. AI Core Requirements (Python FastAPI)

### 8.1 Overview

> **Status: Implemented (Phase 3)**

The AI core is a standalone Python 3.11 microservice built with FastAPI. It is responsible for all LLM interactions — receiving structured requests from the Spring Boot routing server, managing conversation context, assembling prompts, and streaming responses back. The frontend never calls this service directly.

> **Note (dev):** The routing server's chat proxy endpoints are not yet implemented. During development the frontend calls the AI core directly at port 8000. This will be replaced by the routing server proxy in a future sprint.

The AI core also embeds an **MCP (Model Context Protocol) server** that exposes Wheelway-specific tools to the LLM. Rather than hardcoding HTTP calls inside prompt logic, the LLM autonomously decides when to invoke MCP tools (e.g. fetching a route, querying obstacles) based on the user's message. MCP is not a separate service — it runs within the same Python process as the FastAPI app.

### 8.2 Functional Requirements

#### FR-AI-01: Conversational Wheelchair Navigation Assistant

- The AI assistant understands natural-language queries about accessible navigation
- Example queries it must handle:
  - _"Find me a route to Central Park without stairs"_
  - _"Is there an elevator at 42nd Street station?"_
  - _"What is the most accessible path from my current location to the nearest pharmacy?"_
- Responses must be concise, actionable, and mobility-aware

#### FR-AI-02: Contextual Awareness

Each chat request from the routing server includes a context payload:

| Field                  | Type                   | Description                                    |
| ---------------------- | ---------------------- | ---------------------------------------------- |
| `user_location`        | `{ lat, lng }` \| null | Current GPS coordinates of the user            |
| `active_route`         | Route object \| null   | The route currently displayed on the map       |
| `map_center`           | `{ lat, lng }`         | Center coordinates of the current map viewport |
| `conversation_history` | Message[]              | Previous messages in the current session       |

In client applications, `user_location` should be auto-populated from browser/app geolocation when available so users do not need to type their location into chat prompts.

#### FR-AI-03: Streaming Response

- The AI core exposes a Server-Sent Events (SSE) endpoint for streaming
- Token-by-token streaming from the LLM is proxied through the routing server to the frontend
- First token must appear in the UI within **3 seconds** of request submission

#### FR-AI-04: Swappable LLM Backend

- LLM calls are encapsulated in `gemini_service.py` — swapping providers requires implementing a new service module
- Default implementation: **Google Gemini 3.1 Flash Lite Preview** via REST API (`app/gemini_service.py`)
- Model configurable via environment variable `GEMINI_MODEL` (default: `gemini-3.1-flash-lite-preview`)

#### FR-AI-07: Embedded MCP Server

- The AI core runs an MCP server within the same process (no separate container)
- MCP tools are defined in `mcp/tools/` and registered at startup
- The LLM calls MCP tools autonomously based on user intent — no hardcoded routing logic in prompts
- All MCP tool calls that require routing data make internal HTTP calls to the Spring Boot routing server

**MCP Tools:**

| Tool Name                 | Description                                                                                                    | Calls                        |
| ------------------------- | -------------------------------------------------------------------------------------------------------------- | ---------------------------- |
| `get_route`               | Generate a wheelchair-accessible route between two points                                                      | `GET /route/getSingleRoute`  |
| `report_obstacle`         | Report an accessibility obstacle at a given location                                                           | `POST /api/v1/obstacles`     |
| `get_obstacles`           | Retrieve known obstacles near a location                                                                       | `GET /api/v1/obstacles`      |
| `get_map_context`         | Return current map center, active route, and user location                                                     | Internal session state       |
| `get_place_accessibility` | Look up wheelchair accessibility tags (entrance, ramp, door) for a named building via OSM Nominatim + Overpass | OSM Nominatim + Overpass API |

#### FR-AI-05: System Prompt & Persona

- The AI assistant has a defined persona: helpful, calm, accessibility-expert
- System prompt instructs the model to: prioritize safety, cite uncertainty, never invent route data
- System prompt lives in `prompts/system_prompt.txt` and is versioned in git

#### FR-AI-06: Conversation Memory

- Per-session conversation history maintained in-memory for the duration of the browser session
- Maximum context window: last **20 messages** (older messages truncated)
- Redis-backed persistence planned for v1.1 to support multi-device continuity

### 8.3 AI Core API

| Method + Path          | Description                             | Caller                     |
| ---------------------- | --------------------------------------- | -------------------------- |
| `POST /chat`           | Synchronous LLM call with full response | Spring Boot routing server |
| `GET /chat/stream`     | SSE stream of LLM token output          | Spring Boot routing server |
| `DELETE /session/{id}` | Clear session conversation history      | Spring Boot routing server |
| `GET /health`          | Health check endpoint                   | Docker / Kubernetes        |

> The MCP server runs as an internal transport within the Python process and is **not exposed externally**. It is accessible only to the LLM client inside the AI core.

### 8.4 Request / Response Schema

**ChatRequest** (`POST /chat`)

```json
{
  "session_id": "string",
  "message": "string (max 500 chars)",
  "context": {
    "user_location": { "lat": 40.7128, "lng": -74.006 },
    "active_route": "Route object | null",
    "map_center": { "lat": 40.7128, "lng": -74.006 }
  }
}
```

**ChatResponse**

```json
{
  "session_id": "string",
  "message": "string",
  "map_action": {
    "type": "pan | route",
    "payload": {}
  },
  "tokens_used": 312
}
```

---

## 9. User Stories

### 9.1 Navigation

| Story                                                                                                                    | Acceptance Criteria                                                                    |
| ------------------------------------------------------------------------------------------------------------------------ | -------------------------------------------------------------------------------------- |
| As a wheelchair user, I want to search for a route from my current location to a destination, so I can get there safely. | Route displayed within 10s. Only accessible paths shown. Distance and time summarized. |
| As a wheelchair user, I want to see ramp locations on my route, so I know where to expect inclines.                      | Ramp icons rendered at correct GPS coordinates on the polyline.                        |
| As a wheelchair user, I want turn-by-turn directions, so I can navigate without looking at the map constantly.           | Step panel updates as route progresses. Each step has icon + text instruction.         |
| As a caregiver, I want to plan a route in advance without being on-location, so I can prepare for an outing.             | Route generation works without user GPS location (manual origin input).                |

### 9.2 AI Chat

| Story                                                                                                                                   | Acceptance Criteria                                                                      |
| --------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------- |
| As a wheelchair user, I want to ask the AI for route recommendations in plain English, so I don't have to know how to use map controls. | AI responds within 3s. Response includes actionable route suggestion or map action.      |
| As a wheelchair user, I want the AI to know where I am, so its suggestions are relevant to my location.                                 | AI context includes GPS coordinates. AI references nearby landmarks correctly.           |
| As a wheelchair user, I want the AI to stream its response, so I don't stare at a blank screen.                                         | First token appears within 3s. Text streams word-by-word.                                |
| As a user, I want to ask follow-up questions in the same chat, so I don't have to repeat context.                                       | Conversation history maintained for the session. AI references prior messages correctly. |

---

## 10. Non-Functional Requirements

### 10.1 Performance

| Requirement                       | Target                 |
| --------------------------------- | ---------------------- |
| Route generation (routing server) | < 2 seconds end-to-end |
| Map tile load (initial)           | < 1.5 seconds on 4G    |
| AI first token (chat)             | < 3 seconds            |
| Frontend bundle size              | < 500KB gzipped        |
| API availability (SLA)            | 99.5% uptime           |

### 10.2 Accessibility _(The platform itself must be accessible)_

- WCAG 2.1 Level AA compliance across the entire web application
- All interactive elements keyboard-navigable with visible focus indicators
- Screen reader compatibility: ARIA labels on map markers, route steps, and chat messages
- Minimum 4.5:1 color contrast ratio for all text
- Touch targets minimum 44×44px on mobile

### 10.3 Security

- All API communication over HTTPS / WSS
- JWT tokens expire after 24 hours; refresh token rotation implemented
- AI core not exposed publicly — accessible only from the routing server's internal network
- User location data never stored without explicit opt-in consent
- GDPR and CCPA compliant data handling; right to deletion honored within 30 days

### 10.4 Scalability

- All services containerized with Docker; orchestrated via docker-compose (dev) or Kubernetes (prod)
- routing server is stateless — horizontally scalable behind a load balancer
- AI core scales independently from routing server — designed for high-concurrency SSE connections
- PostgreSQL with PostGIS for geospatial queries; read replicas for scaling

### 10.5 Developer Experience

- In local Docker Compose development mode, frontend and AI core support live reload from bind-mounted source files
- The development startup command must rebuild images so Dockerfile and dependency changes are applied without manual cleanup

---

## 11. Repository Structure

All components live in a single monorepo for unified AI context and a shared `CLAUDE.md` configuration:

```
wheelway/
├── README.md
├── CLAUDE.md
├── docker-compose.yml
├── Makefile
│
├── routing-server/                  # Java 17 Spring Boot — wheelchair routing engine
│   ├── build.gradle
│   ├── settings.gradle
│   └── src/main/java/com/wheelchair/mypath/
│       ├── controller/
│       ├── service/
│       ├── model/
│       ├── filter/
│       ├── configurations/
│       └── exceptionHandler/
│
├── frontend/                        # React 19 + TypeScript
│   ├── package.json
│   └── src/
│       ├── components/
│       │   ├── Map/
│       │   ├── RoutePanel/
│       │   └── AiChat/              # ChatButton, ChatPanel (SSE streaming)
│       ├── services/                # routingService.ts, chatService.ts
│       └── store/                   # useAppStore.ts (Zustand)
│
└── ai-core/                         # Python 3.11 FastAPI — AI chat + MCP Server
    ├── requirements.txt
    ├── Dockerfile
    └── app/
        ├── main.py                  # FastAPI app entrypoint, route definitions, SSE endpoints
        ├── gemini_service.py        # Agentic LLM loop (Google Gemini 2.0 Flash)
        ├── chat_service.py          # Session management, request orchestration
        ├── mcp/                     # MCP server + tool interface
        │   └── tools/               # get_route.py, report_obstacle.py, get_obstacles.py, get_place_accessibility.py
        ├── models/                  # Pydantic models: ChatRequest, ChatResponse, gemini DTOs
        ├── utils/                   # session_store.py (in-memory, bounded)
        └── prompts/                 # system_prompt.txt
```

---

## 12. Milestones & Delivery Phases

| Phase                       | Scope                                                                                              | Timeline   |
| --------------------------- | -------------------------------------------------------------------------------------------------- | ---------- |
| **Phase 0: Foundation**     | Monorepo setup, CLAUDE.md, docker-compose, CI/CD baseline, design system tokens                    | Week 1     |
| **Phase 1: Map MVP**        | React map canvas, route search UI, routing server routing API integration, polyline rendering      | Weeks 2–3  |
| **Phase 2: Navigation UX**  | Turn-by-turn panel, waypoint icons, ramp markers, route preferences, mobile responsiveness         | Weeks 4–5  |
| **Phase 3: AI Chat**        | AI core FastAPI service, SSE streaming, chat UI widget, routing server proxy, map–chat integration | Weeks 6–7  |
| **Phase 4: Data & Reports** | Obstacle reporting, user feedback, saved places, analytics dashboard                               | Week 8     |
| **Phase 5: Hardening**      | WCAG audit, performance testing, security pen-test, load testing, documentation                    | Weeks 9–10 |
| **Phase 6: Launch**         | Production deployment, monitoring setup, user onboarding, public release                           | Week 11    |

---

## 13. Risks & Mitigations

| Risk                                      | Impact                                  | Mitigation                                                                                               |
| ----------------------------------------- | --------------------------------------- | -------------------------------------------------------------------------------------------------------- |
| Routing API returns inaccessible segments | **High** — safety critical              | Validation layer in routing server; user feedback loop; red-flag inaccessible segments in UI             |
| LLM hallucinations about route data       | **High** — trust damage                 | Ground AI responses in routing server data; instruct model to cite uncertainty; never invent route facts |
| Map tile provider downtime                | **Medium** — core UX broken             | Abstract tile provider; fallback to OSM tiles if Mapbox unavailable                                      |
| SSE connection drops mid-stream           | **Medium** — broken chat UX             | Auto-reconnect with exponential backoff; display partial response with retry button                      |
| WCAG non-compliance                       | **High** — core product promise         | Continuous automated a11y testing in CI (axe-core); scheduled manual screen reader audits                |
| AI core cost overrun                      | **Medium** — LLM costs scale with usage | Token budgets per request; rate limiting at routing server; switch to smaller model for simple queries   |

---

## 14. Open Questions

| Question                                                                                  | Owner                                                                               |
| ----------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------- |
| Which map tile provider: Leaflet + OSM (free) or Mapbox (paid, better styling)?           | Product / Engineering                                                               |
| Should AI chat support voice input (Web Speech API) in v1.0?                              | Product                                                                             |
| What is the conversation memory strategy: in-memory (v1.0) or Redis from day one?         | AI Engineering — **decided: in-memory (v1.0, implemented), Redis planned for v1.1** |
| Should the routing engine support public transit connections alongside wheelchair routes? | Product                                                                             |
| Which LLM do we default to: GPT-4o (OpenAI) or Claude (Anthropic)?                        | AI Engineering — **decided: Google Gemini 2.0 Flash (implemented)**                 |
| Do we need offline map support for areas with poor connectivity?                          | Product / Engineering                                                               |
| Should users be required to create an account, or is anonymous usage supported?           | Product                                                                             |

---

## 15. Glossary

| Term                 | Definition                                                                                                                 |
| -------------------- | -------------------------------------------------------------------------------------------------------------------------- |
| **Accessible Route** | A path navigable by a standard or motorized wheelchair, free of stairs and impassable terrain                              |
| **Curb Cut**         | A ramp built into a curb to allow wheelchair passage from sidewalk to road level                                           |
| **PostGIS**          | A PostgreSQL extension that adds geospatial data types and functions for storing and querying location data                |
| **SSE**              | Server-Sent Events — a one-way HTTP streaming protocol used to push AI token output from server to browser in real time    |
| **LLM**              | Large Language Model — the AI model (GPT-4o or Claude) that powers the conversational assistant                            |
| **WCAG 2.1 AA**      | Web Content Accessibility Guidelines version 2.1, Level AA — the internationally recognized standard for web accessibility |
| **FAB**              | Floating Action Button — the persistent button in the bottom-right of the UI that opens the AI chat panel                  |
| **PRD**              | Product Requirements Document — this document                                                                              |

---

_© 2025 Wheelway. All rights reserved. — End of Document_
