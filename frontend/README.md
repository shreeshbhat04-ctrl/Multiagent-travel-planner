# A2A Travel Planner Frontend

React + Vite frontend for the travel planner backend in [`backend/main.py`](C:/Users/shree/track2/the_project/backend/main.py).

## Features

- Streams `/plan/stream` events from the FastAPI backend
- Surfaces verifier, orchestrator, tool, and planner activity in a live timeline
- Renders the structured itinerary schema from [`agent/itinerary.py`](C:/Users/shree/track2/the_project/agent/itinerary.py)
- Uses Google Maps 3D when `VITE_GOOGLE_MAPS_API_KEY` is configured
- Falls back to a live 2D Google map or internal route projection when 3D is unavailable

## Setup

1. Install dependencies:

```bash
npm install
```

2. Create a frontend env file:

```bash
cp .env.example .env
```

3. Set local values:

- `VITE_API_BASE_URL=http://127.0.0.1:8000`
- `VITE_GOOGLE_MAPS_API_KEY=...` if you want the 3D map layer in the browser

4. Run the frontend:

```bash
npm run dev
```

## Production / Cloud Run

For Cloud Run, the frontend is built into `dist` and served by the FastAPI backend from the same origin.

Recommended production behavior:

- leave `VITE_API_BASE_URL` unset so the app calls `/health`, `/plan`, and `/plan/stream` on the same deployed host
- keep `VITE_GOOGLE_MAPS_API_KEY` set at build time if you want browser-side Google Maps rendering

Build:

```bash
npm run build
```

## Notes

- The backend streaming endpoint is POST-based SSE, so the frontend parses the event stream manually instead of using `EventSource`.
- The backend does not currently persist `_sessions`, so the UI reads the itinerary directly from planner stream events.
- The deployed backend can now serve the built frontend directly, so a separate frontend hosting service is optional.
