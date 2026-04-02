# Wheelway Documentation

> _Every path, accessible._

Wheelway is a wheelchair-accessible navigation platform that enables wheelchair users to independently plan, discover, and navigate routes in the real world. Unlike general-purpose mapping solutions, Wheelway treats accessibility as a first-class concern — every route, every turn, and every recommendation is filtered through the lens of wheelchair usability.

---

## Documentation Index

| Document | Description |
|---|---|
| [Architecture](architecture.md) | System design, component interactions, and data flow |
| [Getting Started](getting-started.md) | Local setup, environment variables, and running the stack |
| [Frontend](frontend.md) | React app components, state management, and services |
| [Routing Server](routing-server.md) | Java Spring Boot routing engine internals |
| [AI Core](ai-core.md) | Python FastAPI AI service, MCP tools, and LLM integration |
| [API Reference](api-reference.md) | All HTTP endpoints with request/response schemas |

---

## What Is Wheelway?

Wheelway is a three-service monorepo:

| Service | Technology | Port | Role |
|---|---|---|---|
| **Frontend** | React 19, TypeScript, Vite, Leaflet | 3000 | Interactive map UI |
| **Routing Server** | Java 17, Spring Boot 3, GraphHopper | 8080 | Wheelchair-accessible route calculation |
| **AI Core** | Python 3.11, FastAPI, Google Gemini | 8000 | Conversational AI navigation assistant |

The platform gives wheelchair users a Google Maps-style experience purpose-built around accessibility — surface types, inclines, ramps, and accessible entrances — backed by an AI assistant that understands natural language navigation requests.

---

## Quick Start

```bash
# Clone and start all services in development mode
git clone <repo>
cd wheel-route
make dev
```

The app is available at `http://localhost:3000`. See [Getting Started](getting-started.md) for full setup details.
