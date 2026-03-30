# A2A Travel Planner Frontend

React + Vite frontend for the travel planner backend in [`backend/main.py`](C:/Users/shree/track2/the_project/backend/main.py).

## Features

- Streams `/plan/stream` events from the FastAPI backend
- Surfaces verifier, orchestrator, tool, and planner activity in a live timeline
- Renders the structured itinerary schema from [`agent/itinerary.py`](C:/Users/shree/track2/the_project/agent/itinerary.py)
- Uses Google Maps 3D when `VITE_GOOGLE_MAPS_API_KEY` is configured
- Falls back to an internal route projection when no browser Maps key is set

## Setup

1. Install dependencies:

```bash
npm install
```

2. Create a frontend env file:

```bash
copy .env.example .env
```

3. Set:

- `VITE_API_BASE_URL=http://127.0.0.1:8000`
- `VITE_GOOGLE_MAPS_API_KEY=...` if you want the 3D map layer in the browser

4. Run the frontend:

```bash
npm run dev
```

## Notes

- The backend streaming endpoint is POST-based SSE, so the frontend parses the event stream manually instead of using `EventSource`.
- The backend does not currently persist `_sessions`, so the UI reads the itinerary directly from planner stream events.
