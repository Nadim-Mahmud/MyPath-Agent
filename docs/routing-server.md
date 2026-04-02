# Routing Server

The routing server is a Java 17 Spring Boot application that generates wheelchair-accessible routes using the GraphHopper routing engine and OpenStreetMap data.

---

## Technology Stack

| Library | Version | Role |
|---|---|---|
| Java | 17 | Language |
| Spring Boot | 3.4.3 | Framework |
| Spring Security | — | API key authentication |
| GraphHopper | 10.2 | Routing engine |
| Osmosis | 0.49.2 | OSM PBF file processing |
| Gradle | 8.7 | Build tool |

---

## Directory Structure

```
routing-server/src/main/java/com/wheelchair/mypath/
├── MypathApplication.java              # Spring Boot entry point
├── configurations/
│   ├── CustomGraphHopperConfig.java    # GraphHopper initialisation and graph loading
│   └── WebConfig.java                  # CORS and security configuration
├── constants/
│   └── Constants.java                  # PBF URL, incline thresholds, cache paths
├── controller/
│   ├── BaseController.java
│   └── RoutingController.java          # REST endpoint handlers
├── cron/
│   └── ScheduledMapUpdateJob.java      # Daily OSM data refresh (1:23 AM UTC)
├── exceptions/
│   └── RouteNotFound.java
├── exceptionHandler/
│   └── GlobalExceptionHandler.java     # Unified HTTP error responses
├── filter/
│   └── ApiKeyFilter.java               # Bearer token validation
├── model/
│   ├── TurnDirection.java
│   ├── PathDetails.java
│   └── (response DTOs)
├── service/
│   └── RoutingService.java             # Route computation and response assembly
└── utils/
    ├── GeoUtils.java                   # Haversine distance, geometry helpers
    ├── GHProfileUtils.java             # GraphHopper wheelchair profile setup
    ├── StringUtils.java
    ├── NumberUtils.java
    ├── DateUtils.java
    └── Utils.java

src/main/resources/
├── application.properties              # Port (8080), API key
├── custom-models/
│   └── wheelchair.json                 # GraphHopper wheelchair routing profile
└── logback-spring.xml                  # Logging configuration
```

---

## API Endpoints

### GET /

Health and liveness check.

**Authentication:** None required.

**Response:** `200 OK` with body `"Hi there.."`

---

### GET /route/getSingleRoute

Generate a wheelchair-accessible route between two coordinates.

**Authentication:** Bearer token required.

```
Authorization: Bearer <api-key>
```

**Query Parameters:**

| Parameter | Type | Required | Description |
|---|---|---|---|
| `srcLat` | double | Yes | Origin latitude |
| `srcLon` | double | Yes | Origin longitude |
| `destLat` | double | Yes | Destination latitude |
| `destLon` | double | Yes | Destination longitude |

**Example:**

```bash
curl -H "Authorization: Bearer 0aed6a955c59dc3c75dba711c6b74edb" \
  "http://localhost:8080/route/getSingleRoute?srcLat=39.507&srcLon=-84.745&destLat=39.513&destLon=-84.738"
```

**Success Response (200):**

```json
{
  "routes": {
    "points": [
      {
        "start_location": { "latitude": 39.507, "longitude": -84.745, "elevation": 285.2 },
        "end_location":   { "latitude": 39.508, "longitude": -84.744, "elevation": 284.8 },
        "points": [
          { "latitude": 39.507, "longitude": -84.745, "elevation": 285.2 },
          { "latitude": 39.508, "longitude": -84.744, "elevation": 284.8 }
        ],
        "surface": "asphalt",
        "distance": { "value": 148.0, "type": "feet", "text": "0.03 mi" },
        "duration": { "value": 21.0,  "type": "second", "text": "0.35 min" },
        "maneuver": "Turn right",
        "incline": 1.4
      }
    ]
  }
}
```

Each object in `points` represents one route segment. Segments are split at maneuver points and grouped by surface type.

**Maneuver values:**
- `Go straight`
- `Turn left` / `Turn slightly left` / `Make a steep left turn`
- `Turn right` / `Turn slightly right` / `Make a steep right turn`
- `Reached` (destination)

**Error Responses:**

| Code | Condition |
|---|---|
| 401 | Missing or invalid `Authorization` header |
| 404 | No accessible route found between the points |
| 500 | Internal server error |

---

## GraphHopper Wheelchair Profile

The routing engine uses a custom wheelchair profile defined in `src/main/resources/custom-models/wheelchair.json`.

The profile:
- **Prioritises** accessible ways (`wheelchair=yes`, `footway`, `pedestrian`)
- **Weights surfaces** — asphalt and concrete preferred; paving stones allowed; unpaved deprioritised
- **Considers incline** — steeper grades are penalised
- **Avoids** stairs, barriers, and impassable terrain
- **Prefers** wheelchair-tagged infrastructure where OSM data is available

The steepness threshold is configured in `Constants.java`. Segments above the threshold are flagged in the route response with their actual incline percentage.

---

## OSM Map Data

### Source

By default the routing server downloads the US dataset:

```
https://download.geofabrik.de/north-america/us-latest.osm.pbf
```

To use a smaller regional extract during development, edit `Constants.java`:

```java
public static final String PBF_URL =
    "https://download.geofabrik.de/north-america/us/maryland-latest.osm.pbf";
```

Available regional extracts at [download.geofabrik.de](https://download.geofabrik.de/).

### Graph Cache

The routing graph is built from the PBF file and stored in:

```
routing-server/myPathDataStore/routing-graph-cache/
```

This directory is gitignored. The cache is loaded at startup (~30 seconds) and kept in memory while the server runs.

### Automated Daily Refresh

`ScheduledMapUpdateJob` runs every day at **1:23 AM UTC**:

1. Downloads fresh OSM PBF from Geofabrik
2. Rebuilds the routing graph in a temp directory
3. Hot-swaps the active graph without restarting the server
4. Removes old PBF files

---

## Authentication

All `/route/*` endpoints require an API key in the `Authorization` header:

```
Authorization: Bearer <api-key>
```

The API key is configured in `src/main/resources/application.properties`:

```properties
api.key=0aed6a955c59dc3c75dba711c6b74edb
```

The `ApiKeyFilter` intercepts all matching requests, extracts the Bearer token, and returns `401` if it does not match.

**Changing the key in development:** Update both `application.properties` and the `VITE_API_KEY` / `ROUTING_API_KEY` environment variables in `docker-compose.yml`.

---

## Build

### With Gradle

```bash
cd routing-server
./gradlew bootJar -x test     # Skip tests for faster build
java -Xmx2g -jar build/libs/mypath-0.0.1-SNAPSHOT.jar
```

### Via Docker Compose

The Dockerfile uses a multi-stage build:
1. Gradle wrapper downloads dependencies and builds the JAR
2. The JAR is copied into a slim JRE image
3. The container starts the JAR as the entry point

---

## Logging

Structured logs are written to stdout and to `mypath_stdout.log`. Log level is `INFO` by default. Configured in `logback-spring.xml`.

Key log events:
- Route request received with source/destination coordinates
- GraphHopper computation time
- Authentication failures (401)
- Route not found (404)
- OSM data refresh start and completion

---

## Planned Features

The following are planned but not yet implemented:

| Feature | Planned Endpoints |
|---|---|
| Obstacle reporting | `GET /api/v1/obstacles`, `POST /api/v1/obstacles`, `PATCH /api/v1/obstacles/{id}/verify` |
| AI chat proxy | `POST /api/v1/chat`, `GET /api/v1/chat/stream`, `DELETE /api/v1/chat/{sessionId}` |
| JWT authentication | Login/signup, Google OAuth 2.0 |
| Route history | `GET /api/v1/routes/{id}`, `POST /api/v1/routes/{id}/feedback` |
| PostgreSQL + PostGIS | Geospatial obstacle storage and route persistence |
| Rate limiting | 100 req/min per IP for routing, 20 req/min for chat |
