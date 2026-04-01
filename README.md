# Wheelway

Wheelchair-accessible navigation platform. Every path, accessible.

---

## Services

| Service        | Technology                        | Port |
|----------------|-----------------------------------|------|
| Frontend       | React 19 + TypeScript + nginx     | 3000 |
| Routing Server | Java 17, Spring Boot, GraphHopper | 8080 |
| AI Core        | Python FastAPI *(planned)*        | 8000 |

---

## Prerequisites

- [Docker](https://docs.docker.com/get-docker/) 24+
- [Docker Compose](https://docs.docker.com/compose/) v2 (bundled with Docker Desktop)
- ~4 GB free disk space (for the OSM graph cache)
- ~2 GB RAM available for the routing server

---

## Running with Docker Compose

### First-time setup

**If you have the pre-built graph cache** (the `routing-server/myPathDataStore/` directory is already present), the routing server loads in ~30 seconds. Just run:

```bash
docker compose up --build
```

Then open [http://localhost:3000](http://localhost:3000).

---

**If the graph cache is missing**, the routing server will automatically download the US OpenStreetMap PBF file from Geofabrik and build the routing graph on first boot. This process:
- Downloads ~1 GB of OSM data
- Builds the wheelchair routing graph (can take 10–30 minutes depending on hardware)
- Stores the result in `routing-server/myPathDataStore/` for future runs

The frontend will wait (via healthcheck) until the routing server is ready before starting.

```bash
docker compose up --build
# Go get a coffee — first boot takes a while if the cache is not present
```

---

### Subsequent runs

The graph cache is persisted in `routing-server/myPathDataStore/` on your host machine. After the first build, starting up is fast:

```bash
docker compose up
```

### Stop

```bash
docker compose down
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

### Frontend

```bash
cd frontend
npm install
npm run dev      # → http://localhost:5173
```

The dev server proxies are not configured by default — the frontend talks directly to `http://localhost:8080` in dev mode.

---

## API Reference

### `GET /route/getSingleRoute`

Generates a wheelchair-accessible route between two coordinates.

**Authentication:** `Authorization: Bearer <api-key>` header required.

| Query Param | Type   | Description              |
|-------------|--------|--------------------------|
| `srcLat`    | double | Origin latitude          |
| `srcLon`    | double | Origin longitude         |
| `destLat`   | double | Destination latitude     |
| `destLon`   | double | Destination longitude    |

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

Each element in `points` is a route segment grouped by surface type and split at each maneuver (turn). Incline is a percentage grade; segments > 5% are flagged in the UI.

---

## Project Structure

```
wheelway/
├── docker-compose.yml
├── README.md
├── routing-server/          # Java 17 Spring Boot — wheelchair routing engine
│   ├── Dockerfile
│   ├── build.gradle
│   ├── myPathDataStore/     # GraphHopper graph cache (gitignored, generated at runtime)
│   └── src/
├── frontend/                # React 19 + TypeScript — map UI
│   ├── Dockerfile
│   ├── nginx.conf
│   └── src/
│       ├── components/      # Map, SearchBar, RoutePanel, AiChat, Preferences
│       ├── services/        # routingService.ts (Axios)
│       ├── store/           # useAppStore.ts (Zustand)
│       └── types/           # route.ts
└── ai-core/                 # Python FastAPI — AI chat assistant (planned)
```

---

## Map Coverage

The routing server uses OpenStreetMap data for wheelchair-accessible routing via [GraphHopper](https://www.graphhopper.com/). On first boot the server downloads the full US OSM dataset. The graph cache is refreshed nightly at 1:23 AM by a built-in scheduler.

To change the covered region, update `PBF_URL` in `routing-server/src/main/java/com/wheelchair/mypath/constants/Constants.java` before building.
