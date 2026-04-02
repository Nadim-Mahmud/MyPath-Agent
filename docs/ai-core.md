# AI Core

The AI core is a Python 3.11 FastAPI microservice that powers the MyPathAgent conversational assistant. It manages conversation sessions, enriches user messages with map context, classifies intent, and runs an agentic LLM loop using Google Gemini with in-process MCP tools.

---

## Technology Stack

| Library | Version | Role |
|---|---|---|
| Python | 3.11 | Language |
| FastAPI | — | HTTP framework |
| Pydantic | — | Request/response validation |
| httpx | — | Async HTTP client (Nominatim, Overpass, Gemini) |
| Google Gemini | 2.0 Flash | LLM backend |

---

## Directory Structure

```
ai-core/app/
├── main.py                     # FastAPI app, middleware, exception handlers, router wiring
├── config.py                   # Settings (Pydantic BaseSettings, reads env vars)
├── constants.py                # All string literals and numeric constants
├── dependencies.py             # Singleton service instances (chat_service, session_store, ...)
├── exceptions.py               # AiCoreError, GeminiError
├── models.py                   # Pydantic request/response models
├── llm/
│   ├── base.py                 # LLMProvider abstract base class
│   ├── types.py                # CompletionResult dataclass
│   └── gemini.py               # GeminiProvider — agentic tool-call loop
├── mcp/
│   ├── base_tool.py            # BaseTool abstract base class
│   ├── server.py               # MCPServer — tool registry and dispatcher
│   └── tools/
│       ├── get_route.py        # Calls routing server GET /route/getSingleRoute
│       ├── geocode_place.py    # Nominatim place search
│       ├── get_place_accessibility.py  # Nominatim + Overpass OSM accessibility lookup
│       ├── get_obstacles.py    # (planned) obstacle query
│       └── report_obstacle.py  # (planned) obstacle reporting
├── routes/
│   ├── chat.py                 # POST /chat, DELETE /session/{id}
│   └── geocode.py              # POST /geocode
└── services/
    ├── chat_service.py         # Core chat orchestration
    ├── session_store.py        # In-memory conversation history
    ├── intent_detector.py      # Keyword-based intent classification
    └── geocoding_service.py    # Nominatim HTTP wrapper

ai-core/prompts/
└── system_prompt.txt           # LLM system prompt (versioned in git)
```

---

## HTTP Endpoints

### POST /chat

Process a chat message and return the AI response.

**Request body:**

```json
{
  "session_id": "abc-123",
  "message": "Take me to the nearest pharmacy",
  "context": {
    "user_location": { "lat": 39.507, "lng": -84.745 },
    "map_center":    { "lat": 39.510, "lng": -84.740 },
    "active_route":  null
  }
}
```

| Field | Type | Required | Description |
|---|---|---|---|
| `session_id` | string | Yes | UUID identifying the conversation session |
| `message` | string | Yes | User's message (max 500 characters) |
| `context.user_location` | `{lat, lng}` | No | Browser GPS coordinates |
| `context.map_center` | `{lat, lng}` | No | Current map viewport centre |
| `context.active_route` | Route object | No | Route currently rendered on the map |

**Response body:**

```json
{
  "session_id": "abc-123",
  "message": "I found a route to CVS Pharmacy (0.3 miles, ~4 min).",
  "route_action": {
    "origin":      { "lat": 39.507, "lng": -84.745, "label": "My Location" },
    "destination": { "lat": 39.512, "lng": -84.739, "label": "CVS Pharmacy" }
  },
  "map_pins": null,
  "response_intent": "route"
}
```

| Field | Type | Description |
|---|---|---|
| `session_id` | string | Echoed from request |
| `message` | string | AI response text (may contain Markdown) |
| `route_action` | object \| null | If set, the frontend auto-fetches this route and renders it on the map |
| `map_pins` | array \| null | Accessibility pins to render (accessible entrances, ramps) |
| `response_intent` | string | Detected intent: `route` \| `accessibility` \| `general` |

**Error responses:**

| Code | Condition |
|---|---|
| 422 | Invalid request body |
| 503 | AI service unavailable (Gemini API error) |
| 500 | Unexpected server error |

---

### DELETE /session/{session_id}

Clear the conversation history for a session.

**Response:**

```json
{ "status": "cleared", "session_id": "abc-123" }
```

---

### POST /geocode

Search for places by name with optional coordinate bias.

**Request body:**

```json
{
  "query": "Starbucks Oxford Ohio",
  "bias_lat": 39.507,
  "bias_lon": -84.745,
  "limit": 5
}
```

**Response:**

```json
{
  "query": "Starbucks Oxford Ohio",
  "results": [
    { "label": "Starbucks, High Street, Oxford, Ohio", "lat": 39.509, "lng": -84.744 }
  ]
}
```

---

### GET /health

Liveness check.

**Response:**

```json
{ "status": "ok", "service": "mypathagent-ai-core" }
```

---

## Chat Pipeline

Every `POST /chat` request goes through this pipeline in `ChatService.chat()`:

```
1. Load session history (SessionStore)
2. Detect intent (IntentDetector)
3. Detect if this is a retry after a failed geocoding attempt
4. Build focused history (last 6 messages, stripping context blocks)
5. Fast-path: if intent=route and GPS available, try routing directly (no LLM)
6. Enrich the user message with GPS context and intent instructions
7. Call GeminiProvider.complete(enriched_message, focused_history)
8. Override apologetic AI messages if a route was actually found
9. Persist turn to session store
10. Return ChatResponse
```

---

## Intent Detection

The `IntentDetector` classifies every incoming message into one of three intents using keyword matching:

| Intent | Trigger keywords |
|---|---|
| `route` | "take me to", "route to", "directions to", "navigate", "how do i get to", "get to", "go to", "find a route" |
| `accessibility` | "accessible", "wheelchair", "ramp", "elevator", "lift", "entrance", "step-free", "disability" |
| `general` | Everything else |

Intent drives:
- Which system prompt instructions the LLM receives
- Whether the fast-path routing attempt runs
- Whether `route_action` or `map_pins` are returned to the frontend

---

## Fast-Path Routing

For common route requests ("take me to X"), the chat service tries to resolve the route without calling the LLM at all:

1. Extract the destination name from the message
2. Check if GPS coordinates are available in the request context
3. If the destination looks like a named place (no street number):
   - Call `get_place_accessibility` to find coordinates and accessible entrances
4. If it looks like a street address:
   - Call `geocode_place` with 10 candidates (more for full addresses)
5. Try routing to each accessible entrance coordinate, then fall back to the building centroid
6. If a route is found, return a `ChatResponse` immediately — no Gemini API call made

This significantly reduces latency and API costs for the most common usage pattern.

---

## Agentic LLM Loop (GeminiProvider)

When the fast-path fails or the intent is not `route`, the `GeminiProvider` runs an agentic loop:

```
for round in 1..max_tool_rounds:
    response = POST to Gemini generateContent API
               (with system prompt, conversation history, tool declarations)

    if no functionCall in response:
        extract text, build route_action from last get_route call
        return CompletionResult

    for each functionCall:
        result = MCPServer.execute_tool(name, args)
        accumulate: last_route_call_args, geocoded_locations, map_pins

    append model content + tool responses to conversation
    continue loop

# If max_tool_rounds reached:
final_response = POST to Gemini (no more tool calls forced)
return CompletionResult
```

The loop terminates when Gemini returns a pure text response (no tool calls) or when `max_tool_rounds` is reached (default: 5).

---

## MCP Tools

The `MCPServer` is an in-process tool registry. It is not a separate service. Tools are registered at startup and their declarations are passed to the Gemini API so the LLM can call them.

### get_route

Fetches a wheelchair-accessible route from the routing server.

| Parameter | Type | Description |
|---|---|---|
| `src_lat` | number | Origin latitude |
| `src_lon` | number | Origin longitude |
| `dest_lat` | number | Destination latitude |
| `dest_lon` | number | Destination longitude |

Returns: total distance (miles), estimated minutes, surface list, steep segment count, up to 12 route steps.

### geocode_place

Searches for a place name using Nominatim.

| Parameter | Type | Description |
|---|---|---|
| `query` | string | Place name or address |
| `bias_lat` | number | Optional latitude bias |
| `bias_lon` | number | Optional longitude bias |
| `limit` | number | Max results (default 5) |

Returns: list of `{label, lat, lng}` results.

### get_place_accessibility

Looks up wheelchair accessibility data for a named building using OpenStreetMap Nominatim and the Overpass API.

| Parameter | Type | Description |
|---|---|---|
| `place_name` | string | Building or place name |
| `bias_lat` | number | Optional latitude hint |
| `bias_lon` | number | Optional longitude hint |

Returns:
- `found` — whether the place was found in OSM
- `place` — resolved place name
- `lat`, `lon` — coordinates
- `place_tags` — `{wheelchair, ramp, step_count, kerb, ...}`
- `entrances` — list of entrance nodes with `{entrance, wheelchair, door, ramp, lat, lon}`
- `ramps` — list of ramp nodes with coordinates

**Overpass query strategy:**
1. First request: member query — fetches the building element and all its member nodes in one round-trip (covers entrances mapped as building members)
2. Fallback request: radius query — searches for entrance and ramp nodes within 50 m of the building centroid if the member query finds none

### get_obstacles

(Planned) Returns known accessibility obstacles near a location.

### report_obstacle

(Planned) Reports a new accessibility obstacle at a location.

---

## Session Store

`SessionStore` maintains in-memory per-session conversation history:

- Storage: Python dict keyed by `session_id`
- Maximum history: last **20 messages** per session
- History format: `[{"role": "user"|"model", "parts": [{"text": "..."}]}]`
- Cleared by `DELETE /session/{session_id}` or when the user clicks "New chat"

The LLM only receives the last **6 messages** per request (`_MAX_FOCUSED_HISTORY_MESSAGES`) to reduce token usage and context interference from stale information.

---

## Message Enrichment

Before sending a message to Gemini, `ChatService._enrich_message()` appends:

```
[Instruction] Prioritize this latest user request.
[Intent] route
[Intent handling] User is asking for route planning. Prioritize route computation.

[Context]
User GPS: 39.507, -84.745
If user asks from current location, use this User GPS as route origin.
Map centre: 39.510, -84.740
User has active route.
Active route accessibility summary (coordinates removed):
{"segments_total":14,"summary":{"surface_counts":{"asphalt":12,"paving_stones":2},...}}
```

The `[Context]` block is stripped from messages before they are stored in history (to avoid accumulating duplicate context across turns).

---

## Retry Recovery

When a user retries with a more specific location after a failed geocoding attempt, the pipeline:

1. Detects the retry by scanning history for a prior negative geocoding message
2. Strips that negative message from the history sent to the LLM (prevents negative anchoring)
3. Uses 10 geocoding candidates instead of 5 for addresses containing street keywords (number + "street", "avenue", etc.)
4. Informs the LLM: "Previously failed lookups do not preclude success with a more specific address"

---

## Configuration

All settings are defined in `app/config.py` using Pydantic `BaseSettings` and read from environment variables:

| Variable | Default | Description |
|---|---|---|
| `GEMINI_API_KEY` | — | Required. Google Gemini API key |
| `GEMINI_MODEL` | `gemini-2.0-flash` | Gemini model identifier |
| `GEMINI_GENERATE_URL` | Gemini REST endpoint | Full URL to `generateContent` |
| `ROUTING_SERVER_URL` | `http://routing-server:8080` | Internal routing server URL |
| `ROUTING_API_KEY` | — | Bearer token for routing server |
| `MAX_TOOL_ROUNDS` | `5` | Max agentic loop iterations |

---

## System Prompt

The LLM system prompt is stored in `prompts/system_prompt.txt` and versioned in git. It defines the AI persona:

- Helpful, calm, accessibility-expert
- Prioritise safety and cite uncertainty
- Never invent route data — always ground responses in tool results
- Respond concisely and action-oriented

---

## Extending the LLM Backend

The `LLMProvider` abstract class in `app/llm/base.py` defines the interface:

```python
class LLMProvider(ABC):
    @abstractmethod
    def complete(self, user_message: str, history: list[dict]) -> CompletionResult:
        ...

    @property
    @abstractmethod
    def tool_declarations(self) -> list[dict]:
        ...
```

To add a new LLM backend (e.g. Claude, GPT-4o):
1. Create a new class in `app/llm/` that extends `LLMProvider`
2. Implement `complete()` and `tool_declarations`
3. Swap the instantiation in `app/dependencies.py`

---

## Adding a New MCP Tool

1. Create a file in `app/mcp/tools/` extending `BaseTool`:

```python
class MyTool(BaseTool):
    @property
    def name(self) -> str:
        return "my_tool"

    @property
    def declaration(self) -> dict:
        return {
            "name": self.name,
            "description": "...",
            "parameters": {
                "type": "OBJECT",
                "properties": { ... },
                "required": [...],
            },
        }

    def execute(self, args: dict) -> dict:
        # Tool logic here
        return { ... }
```

2. Register it in `MCPServer._register_default_tools()` in `app/mcp/server.py`

The tool will automatically appear in the next Gemini API call's tool declarations.
