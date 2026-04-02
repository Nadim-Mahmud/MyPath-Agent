# Frontend

The MyPathAgent frontend is a React 19 single-page application built with TypeScript and Vite. It provides a full-screen interactive map experience for searching wheelchair-accessible routes and chatting with the AI assistant.

---

## Technology Stack

| Library | Version | Role |
|---|---|---|
| React | 19.2.4 | UI framework |
| TypeScript | ~5.9.3 | Type safety |
| Vite | 8.0.1 | Build tool and dev server |
| Leaflet | 1.9.4 | Map rendering |
| React-Leaflet | 5.0.0 | Leaflet React bindings |
| Zustand | 5.0.12 | Global state management |
| Axios | 1.14.0 | HTTP client |
| React-Markdown | 10.1.0 | Markdown rendering in chat |

---

## Directory Structure

```
frontend/src/
├── main.tsx                    # React DOM entry point
├── App.tsx                     # Root component — layout and top-level wiring
├── App.css                     # App-level styles
├── index.css                   # Global styles and CSS variables
├── components/
│   ├── Map/
│   │   └── MapCanvas.tsx       # Leaflet map, route polylines, accessibility pins
│   ├── SearchBar/
│   │   └── SearchBar.tsx       # Origin/destination input with autocomplete
│   ├── RoutePanel/
│   │   └── RoutePanel.tsx      # Turn-by-turn navigation panel
│   ├── AiChat/
│   │   ├── ChatButton.tsx      # Floating action button that opens the chat
│   │   └── ChatPanel.tsx       # Chat window with message history and input
│   └── Preferences/
│       └── PreferencesPanel.tsx  # Accessibility preference settings
├── services/
│   ├── routingService.ts       # Calls GET /route/getSingleRoute
│   └── chatService.ts          # Calls POST /chat and DELETE /session/{id}
├── store/
│   └── useAppStore.ts          # Zustand store — all application state
├── types/
│   └── route.ts                # TypeScript interfaces for route API responses
└── assets/                     # Static icons and images
```

---

## Components

### App.tsx — Root Layout

The root component orchestrates the entire layout. It renders the map as the full-screen base layer and overlays all other panels. Key responsibilities:

- Dark mode toggle with theme persistence via `data-theme` attribute
- Info button with help text and legend
- Error toast notification display
- Conditionally renders `RoutePanel` when a route is active
- Conditionally renders `ChatPanel` when chat is open

---

### MapCanvas.tsx — Interactive Map

Renders a Leaflet map with OpenStreetMap tiles and all dynamic content:

**Route polylines** — colour-coded by surface type per segment:

| Surface | Colour | Hex |
|---|---|---|
| Asphalt / concrete | Blue | `#1A56DB` |
| Paving stones / sett | Amber | `#f59e0b` |
| Unpaved / gravel / dirt | Red | `#ef4444` |
| Unknown | Gray | `#6b7280` |

**Markers:**
- Green marker at the route origin
- Red marker at the route destination
- Accessibility pins from AI chat (♿ for accessible entrances, ramp icon for ramps)

**Interactions:**
- Click anywhere on the map to set origin or destination (whichever field is active in SearchBar)
- `flyTo` animation when a location is selected from the search autocomplete

**Props-free design:** MapCanvas reads everything from the Zustand store directly — it does not accept props.

---

### SearchBar.tsx — Location Search

Dual-field origin/destination search with autocomplete and geolocation.

**Autocomplete flow:**
1. User types in either field — debounced 300ms
2. `POST /geocode` called with the query text and optional bias coordinates (current map centre)
3. Up to 5 suggestions rendered in a dropdown
4. User selects a suggestion → store is updated → route is auto-fetched if both fields are populated

**Geolocation:**
- GPS icon button on each field calls `navigator.geolocation.getCurrentPosition()`
- Resolves the coordinate to a label via reverse geocoding
- Sets the field and triggers route fetch if both points are ready

**Active field tracking:** The store's `activeField` ('origin' | 'destination' | null) determines which field a map click or GPS button press populates.

---

### RoutePanel.tsx — Turn-by-Turn Directions

A slide-in panel on the left side of the screen displaying the full route details.

**Header:** Total distance and estimated travel time.

**Surface breakdown:** A visual summary of surface type percentages.

**Step list:** Each step shows:
- Maneuver icon (left, right, U-turn, straight, destination)
- Instruction text
- Distance and duration
- Surface type badge (colour-coded)
- Incline warning badge for grades > 5%

Steps are highlighted on hover. The panel is closed by clearing the active route from the store.

---

### ChatPanel.tsx — AI Chat Interface

A chat window that communicates with the AI Core.

**Message display:**
- User messages right-aligned
- AI messages left-aligned with Markdown rendering
- Typing indicator while waiting for response

**Input:**
- Text field with 500-character limit
- Send on Enter or click
- Voice input via browser `SpeechRecognition` API
- Disabled while AI is responding

**Context sent with every message:**
- `user_location` — browser geolocation coordinates if available
- `map_center` — current map viewport centre
- `active_route` — the full route object if one is displayed

**Route integration:** When the AI response includes a `route_action`, the frontend automatically:
1. Populates origin and destination in SearchBar
2. Calls the routing server to fetch the route
3. Renders the route polyline on the map

**Session management:** A "New chat" button calls `DELETE /session/{session_id}` to clear server-side history, then clears local message history.

---

### PreferencesPanel.tsx — Accessibility Preferences

A settings panel for user-configurable routing constraints:

| Setting | Type | Description |
|---|---|---|
| Max incline | Slider 0–8% | Maximum grade to include in routes |
| Avoid cobblestones | Toggle | Exclude paving stone surfaces |
| Prefer covered routes | Toggle | Prefer sheltered paths |

Preferences are stored in the Zustand store. They are not yet wired into the routing API call (planned).

---

## State Management (Zustand)

All application state lives in a single Zustand store at [src/store/useAppStore.ts](../frontend/src/store/useAppStore.ts).

### State Shape

```typescript
// Route
route: RouteResponse | null        // Active route from routing server
activeStepIndex: number            // Highlighted step in RoutePanel

// UI
isLoading: boolean                 // Route fetch in progress
error: string | null               // Error message for toast
darkMode: boolean                  // Theme toggle
chatOpen: boolean                  // Chat panel visibility

// Chat
chatMessages: ChatMessage[]        // Displayed message history
chatSessionId: string              // UUID per browser session
isChatLoading: boolean             // AI request in progress

// Location inputs
origin: LocationPoint | null       // { lat, lng, label }
destination: LocationPoint | null
activeField: 'origin' | 'destination' | null

// Map
userPosition: [number, number] | null  // Browser geolocation
flyTo: FlyToTarget | null              // Triggers map pan/zoom animation
mapPins: MapPin[]                      // AI-placed accessibility pins

// Preferences
preferences: {
  maxIncline: number
  avoidCobblestones: boolean
  preferCovered: boolean
}
```

### Key Actions

| Action | Effect |
|---|---|
| `setRoute(route)` | Stores route; triggers RoutePanel to open |
| `clearRoute()` | Removes route and closes RoutePanel |
| `setOrigin(point)` | Updates origin field |
| `setDestination(point)` | Updates destination field |
| `setActiveField(field)` | Determines which field a map click populates |
| `addChatMessage(msg)` | Appends a message to the chat history |
| `clearChatMessages()` | Resets chat history |
| `setFlyTo(target)` | Triggers map animation to a location |
| `setMapPins(pins)` | Renders accessibility pins on map |
| `toggleDarkMode()` | Switches theme |

---

## API Service Layer

### routingService.ts

```typescript
fetchRoute(srcLat, srcLon, destLat, destLon): Promise<RouteResponse>
```

- Calls `GET /route/getSingleRoute` on the routing server
- Attaches `Authorization: Bearer <VITE_API_KEY>`
- Returns the route JSON or throws a typed error

### chatService.ts

```typescript
sendChat(sessionId, message, context): Promise<ChatResponse>
clearSession(sessionId): Promise<void>
```

- `sendChat` calls `POST /chat` on the AI Core
- `clearSession` calls `DELETE /session/{sessionId}`
- Base URL: `VITE_AI_CORE_URL` (defaults to `http://localhost:8000` in dev)

---

## TypeScript Types

### RouteResponse

```typescript
interface Coordinate {
  latitude: number
  longitude: number
  elevation: number
}

interface RoutePoint {
  start_location: Coordinate
  end_location: Coordinate
  points: Coordinate[]          // Polyline points for this segment
  surface: string               // "asphalt" | "paving_stones" | "unpaved" | ...
  distance: { value: number; type: string; text: string }
  duration: { value: number; type: string; text: string }
  maneuver: string              // "Turn left" | "Turn right" | "Go straight" | "Reached"
  incline: number               // Grade percentage (negative = downhill)
}

interface RouteResponse {
  routes: { points: RoutePoint[] }
}
```

---

## Build

### Development

```bash
cd frontend
npm install
npm run dev       # Vite dev server with HMR
```

### Production

```bash
npm run build     # Outputs to dist/
npm run preview   # Preview the production build locally
```

### Docker

The Dockerfile has three stages:
- **builder** — Node 20, runs `npm ci && npm run build`
- **development** — Node 20, runs Vite dev server with polling file watcher
- **production** — nginx:alpine, serves `dist/` with the included `nginx.conf`

---

## Styling

- Global CSS variables for theme colours in `index.css`
- Dark mode applied via `data-theme="dark"` on `<html>`
- Component-scoped CSS files alongside each component
- No CSS-in-JS or Tailwind — plain CSS only
- Minimum touch target size: 44×44px
- Colour contrast: WCAG 2.1 AA (minimum 4.5:1 for text)
