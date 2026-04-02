# Getting Started

## Prerequisites

| Tool | Minimum Version | Purpose |
|---|---|---|
| Docker | 24.x | Container runtime |
| Docker Compose | 2.x | Multi-service orchestration |
| GNU Make | 3.x | Build shortcuts |
| Node.js | 20.x | Frontend development (optional, for running outside Docker) |
| Java | 17 | Routing server development (optional) |
| Python | 3.11 | AI core development (optional) |

---

## Environment Variables

Copy or create a `.env` file at the repo root. The default `.env` sets:

```bash
ENV=development
```

Each service has its own environment configuration in `docker-compose.yml`. The required secrets are:

### AI Core

| Variable | Required | Description |
|---|---|---|
| `GEMINI_API_KEY` | Yes | Google Gemini API key |
| `GEMINI_MODEL` | No | Gemini model ID (default: `gemini-2.0-flash`) |
| `ROUTING_SERVER_URL` | No | Internal URL of the routing server (default: `http://routing-server:8080`) |
| `ROUTING_API_KEY` | No | Bearer token for the routing server (must match `api.key` in routing server config) |
| `MAX_TOOL_ROUNDS` | No | Max LLM tool-call iterations per request (default: `5`) |

### Routing Server

| Variable | Required | Description |
|---|---|---|
| `api.key` | Yes | Static API key in `application.properties` (default: `0aed6a955c59dc3c75dba711c6b74edb`) |

### Frontend

| Variable | Required | Description |
|---|---|---|
| `VITE_AI_CORE_URL` | No | AI core base URL visible to the browser (default: `http://localhost:8000`) |
| `VITE_API_BASE_URL` | No | Routing server base URL (empty = relative path proxied by nginx) |
| `VITE_API_KEY` | No | Bearer token sent to the routing server (must match routing server `api.key`) |

---

## Running the Full Stack

### Development (recommended)

```bash
make dev
```

This rebuilds images and starts all services with hot-reload. Changes to frontend source files and AI core source files take effect immediately without restarting.

Access the app at **http://localhost:3000**.

### Production

```bash
make prod
```

Builds an optimised frontend bundle and serves it via nginx. The AI core runs without auto-reload.

### Stop All Services

```bash
make down
```

---

## Service-by-Service Development

### Frontend Only

```bash
cd frontend
npm install
npm run dev
```

Starts the Vite dev server at `http://localhost:5173`. Expects the routing server at port 8080 and the AI core at port 8000.

### AI Core Only

```bash
cd ai-core
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

### Routing Server Only

```bash
cd routing-server
./gradlew bootRun
```

The routing server downloads OSM data and builds its graph cache on first run. This can take several minutes depending on the region configured.

---

## First-Run Graph Cache

The routing server builds a GraphHopper graph cache from OpenStreetMap data on startup. By default it downloads the US dataset from Geofabrik (~10 GB). To use a smaller regional dataset during development, edit `Constants.java`:

```java
// routing-server/src/main/java/com/wheelchair/mypath/constants/Constants.java
public static final String PBF_URL =
    "https://download.geofabrik.de/north-america/us/maryland-latest.osm.pbf";
```

Available regional extracts: Maryland, Ohio, Wisconsin, and any other region from [Geofabrik](https://download.geofabrik.de/).

The cache is stored in `routing-server/myPathDataStore/routing-graph-cache/` and is gitignored. Delete it to force a rebuild.

---

## Verifying the Stack

Once all services are running, check each is healthy:

```bash
# Frontend
curl http://localhost:3000

# AI Core health check
curl http://localhost:8000/health
# Expected: {"status":"ok","service":"mypathagent-ai-core"}

# Routing server health check
curl http://localhost:8080/
# Expected: "Hi there.."

# Test a route
curl -H "Authorization: Bearer 0aed6a955c59dc3c75dba711c6b74edb" \
  "http://localhost:8080/route/getSingleRoute?srcLat=39.5&srcLon=-84.7&destLat=39.51&destLon=-84.71"

# Test geocoding
curl -X POST http://localhost:8000/geocode \
  -H "Content-Type: application/json" \
  -d '{"query":"Oxford Ohio","limit":5}'
```

---

## Common Issues

### Routing server takes too long to start

The graph cache must load before the server accepts requests. Wait 30–90 seconds after the container starts. Check logs with:

```bash
docker compose logs -f routing-server
```

Look for a line containing `Started MypathApplication`.

### AI chat returns no response

Check that `GEMINI_API_KEY` is set and valid. The AI core logs every request:

```bash
docker compose logs -f ai-core
```

### Geocoding returns no results

Nominatim is a public API with rate limits. If you see timeouts, wait a moment and retry. For heavy development usage, consider running a local Nominatim instance.
