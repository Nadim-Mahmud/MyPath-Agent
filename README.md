# Wheelway

Wheelchair-accessible navigation platform. Every path, accessible.

---

## Services

| Service        | Technology                                        | Port |
| -------------- | ------------------------------------------------- | ---- |
| Frontend       | React 19 + TypeScript + Vite (dev) / nginx (prod) | 3000 |
| Routing Server | Java 17, Spring Boot, GraphHopper                 | 8080 |
| AI Core        | Python 3.11, FastAPI, Gemini 2.0 Flash, MCP tools | 8000 |

---

## Prerequisites

- [Docker](https://docs.docker.com/get-docker/) 24+
- [Docker Compose](https://docs.docker.com/compose/) v2 (bundled with Docker Desktop)
- ~4 GB free disk space (for the OSM graph cache)
- ~2 GB RAM available for the routing server

---

## Running with Docker Compose

The project supports two modes selected by the `ENV` variable (defaults to `development`):

| Mode          | Frontend                                           | Command     |
| ------------- | -------------------------------------------------- | ----------- |
| `development` | Vite dev server + AI Core hot reload on every save | `make dev`  |
| `production`  | nginx serving an optimised static build            | `make prod` |

### Development (hot reload)

```bash
make dev
```

Then open [http://localhost:3000](http://localhost:3000). Changes to `frontend/src/` reload instantly without rebuilding the image.

In development, `ai-core/app/` and `ai-core/prompts/` are bind-mounted and FastAPI runs with auto-reload, so AI Core code changes are reflected immediately. `make dev` also runs with `--build` to pick up Dockerfile or dependency changes.

### Production build

```bash
make prod
# Builds the optimised bundle and serves it via nginx
```

### Stop

```bash
make down
```

---

### First-time setup notes

**If you have the pre-built graph cache** (the `routing-server/myPathDataStore/` directory is already present), the routing server loads in ~30 seconds.

**If the graph cache is missing**, the routing server will automatically download the US OpenStreetMap PBF file from Geofabrik and build the routing graph on first boot. This process:

- Downloads ~1 GB of OSM data
- Builds the wheelchair routing graph (can take 10–30 minutes depending on hardware)
- Stores the result in `routing-server/myPathDataStore/` for future runs

The frontend waits (via Docker healthcheck) until both the routing server and AI core are ready before starting.

```bash
make dev
# Go get a coffee — first boot takes a while if the cache is not present
```

---

### Subsequent runs

The graph cache is persisted in `routing-server/myPathDataStore/` on your host machine. After the first build, starting up is fast:

```bash
make dev   # or: make prod
```

---

## Running Services Individually (Development)

### Routing Server

```bash
cd routing-server

# Build the JAR (requires Java 17 + Gradle or the bundled ./gradlew)
./gradlew bootJar -x test

# Run (default port 8080)
java -Xmx2g -jar build/libs/mypath-0.0.1-SNAPSHOT.jar
```

The server is ready when you see `GraphHopper loaded` in the logs. Test it:

```bash
curl -H "Authorization: Bearer MYPATHg5rDJhV2ThPlHsbx1PUV6omQSHHno2YehXASoKoiSIrIh7Wz38ZUKLI9nGcHIHxIZgJQ20TwpOet7dpvnandXGenGzf9E7LGu8wLozshUrQcGYcq61g8bTL5Bi" \
  "http://localhost:8080/route/getSingleRoute?srcLat=40.7128&srcLon=-74.006&destLat=40.7580&destLon=-73.9855"
```

### AI Core

```bash
cd ai-core

# Set your Gemini API key first
export GEMINI_API_KEY=your-key-here

pip install -r requirements.txt

# Run (default port 8000)
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Test the AI core:

```bash
# Health check
curl http://localhost:8000/health

# Send a chat message
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "test-session",
    "message": "Find me an accessible route from Times Square to Central Park",
    "context": {
      "user_location": { "lat": 40.7580, "lng": -73.9855 },
      "map_center": { "lat": 40.7580, "lng": -73.9855 }
    }
  }'

# Stream a response (SSE)
curl "http://localhost:8000/chat/stream?session_id=test&message=What+are+curb+cuts%3F"
```

### Frontend

```bash
cd frontend
npm install
npm run dev      # → http://localhost:5173
```

---

## AI Core — Architecture

The AI core is a **Python 3.11 FastAPI** microservice powered by **Google Gemini 2.0 Flash** with embedded **MCP (Model Context Protocol) tools**. It calls the Gemini REST API directly via `httpx` and runs an agentic tool-calling loop.

```
Frontend (React)
    │  SSE / POST  (direct in dev; via routing server proxy in prod)
    ▼
AI Core (FastAPI :8000)
    │  Agentic loop (gemini_service.py)
    ▼
Gemini 2.0 Flash ──► mcp_server.py
                          │
                          ├── get_route       → GET /route/getSingleRoute  (routing server :8080)
                          ├── get_obstacles   → planned
                          └── report_obstacle → planned
```

### MCP Tools

| Tool              | Description                                           | Status                 |
| ----------------- | ----------------------------------------------------- | ---------------------- |
| `get_route`       | Fetch wheelchair-accessible route from routing server | Implemented            |
| `report_obstacle` | Report an accessibility barrier at a location         | Stub (storage planned) |
| `get_obstacles`   | Retrieve known obstacles near a location              | Stub (storage planned) |

### Configuration (environment variables)

| Env Var              | Default                         | Description                   |
| -------------------- | ------------------------------- | ----------------------------- |
| `GEMINI_API_KEY`     | _(required)_                    | Google Gemini API key         |
| `GEMINI_MODEL`       | `gemini-3.1-flash-lite-preview` | Gemini model ID               |
| `ROUTING_SERVER_URL` | `http://routing-server:8080`    | Internal routing server URL   |
| `ROUTING_API_KEY`    | _(set in compose)_              | Bearer key for routing server |

---

## API Reference

### Routing Server

#### `GET /route/getSingleRoute`

Generates a wheelchair-accessible route between two coordinates.

**Authentication:** `Authorization: Bearer <api-key>` header required.

| Query Param | Type   | Description           |
| ----------- | ------ | --------------------- |
| `srcLat`    | double | Origin latitude       |
| `srcLon`    | double | Origin longitude      |
| `destLat`   | double | Destination latitude  |
| `destLon`   | double | Destination longitude |

**Example:**

```bash
GET http://localhost:8080/route/getSingleRoute?srcLat=40.7128&srcLon=-74.006&destLat=40.7580&destLon=-73.9855
Authorization: Bearer <api-key>
```

**Response:**

```json
{
  "routes": {
    "points": [
      {
        "start_location": { "latitude": 40.712, "longitude": -74.006, "elevation": 5.1 },
        "end_location":   { "latitude": 40.713, "longitude": -74.005, "elevation": 4.8 },
        "points": [ ... ],
        "surface": "asphalt",
        "distance": { "value": 264.0, "type": "feet", "text": "0.05 mi" },
        "duration": { "value": 36.0,  "type": "second", "text": "0.60 min" },
        "maneuver": "turn-right",
        "incline": 1.2
      }
    ]
  }
}
```

---

### AI Core

#### `POST /chat`

Synchronous LLM response (full message returned at once).

```json
{
  "session_id": "string",
  "message": "Find me an accessible route to Central Park",
  "context": {
    "user_location": { "lat": 40.7128, "lng": -74.006 },
    "map_center": { "lat": 40.7128, "lng": -74.006 },
    "active_route": null
  }
}
```

#### `GET /chat/stream`

SSE streaming response. Query params: `session_id`, `message`, `context` (JSON string).

Each SSE event: `data: {"token": "..."}` or `data: [DONE]`

#### `DELETE /session/{session_id}`

Clear conversation history for a session.

#### `GET /health`

Returns `{"status": "ok", "service": "wheelway-ai-core"}`.

---

## Project Structure

```
wheelway/
├── docker-compose.yml
├── Makefile                 # make dev / make prod / make down
├── .env                     # ENV=development (docker-compose target selector)
├── README.md
├── routing-server/          # Java 17 Spring Boot — wheelchair routing engine
│   ├── Dockerfile
│   ├── build.gradle
│   ├── myPathDataStore/     # GraphHopper graph cache (gitignored, generated at runtime)
│   └── src/
├── frontend/                # React 19 + TypeScript — map UI
│   ├── Dockerfile           # 3-stage: builder / development / production
│   ├── nginx.conf
│   └── src/
│       ├── components/      # Map, SearchBar, RoutePanel, AiChat, Preferences
│       ├── services/        # routingService.ts, chatService.ts
│       ├── store/           # useAppStore.ts (Zustand)
│       └── types/           # route.ts
└── ai-core/                 # Python 3.11 FastAPI — AI chat assistant (Gemini + MCP)
    ├── Dockerfile           # python:3.11-slim, pip install, uvicorn
    ├── requirements.txt
    ├── prompts/
    │   └── system_prompt.txt
    └── app/
        ├── main.py          # FastAPI app, routes: /chat, /chat/stream, /session, /health
        ├── config.py        # Env vars (GEMINI_API_KEY, ROUTING_SERVER_URL, …)
        ├── models.py        # Pydantic models: ChatRequest, ChatResponse, ChatContext
        ├── session_store.py # In-memory session store (bounded deque, thread-safe)
        ├── gemini_service.py# Agentic loop — calls Gemini REST API via httpx
        ├── chat_service.py  # Orchestrates session + Gemini + context enrichment
        └── mcp/
            ├── mcp_server.py        # Tool registry + dispatcher
            └── tools/
                ├── get_route.py         # Calls routing-server GET /route/getSingleRoute
                ├── report_obstacle.py   # Stub — storage planned
                └── get_obstacles.py     # Stub — storage planned
```

---

## Map Coverage

The routing server uses OpenStreetMap data for wheelchair-accessible routing via [GraphHopper](https://www.graphhopper.com/). On first boot the server downloads the full US OSM dataset. The graph cache is refreshed nightly at 1:23 AM by a built-in scheduler.

To change the covered region, update `PBF_URL` in `routing-server/src/main/java/com/wheelchair/mypath/constants/Constants.java` before building.
