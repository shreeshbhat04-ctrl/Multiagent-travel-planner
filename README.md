# A2A Travel Planner

**Multi-Agent Travel Planning with CaMeL Security, MCP Data Fetching, and 3D Globe Frontend**

A LangGraph-powered multi-agent system that plans complete travel itineraries using the Agent2Agent (A2A) protocol pattern. A CaMeL security verifier gates all requests, an Orchestrator extracts intent, a Data Fetcher gathers live data via MCP tools (Google Maps, weather, flights, BigQuery), and a Planner constructs optimized daily schedules.

## Architecture

```
User (NL Query) → Verifier → [Safe?]
                       │
                 (No)  └─→ REJECT + END
                 (Yes) └─→ Orchestrator → [Extract Params]
                                 │
                           (Vague) └─→ Ask clarifying question + END
                           (Ready) └─→ Data Fetcher ↔ MCP Tools
                                            │
                                            ├─ 📍 Google Places API
                                            ├─ 🌤️ OpenWeatherMap
                                            ├─ ✈️ AviationStack
                                            ├─ 🗺️ Google Routes API
                                            └─ 📊 BigQuery
                                            │
                                       Planner → Structured JSON Itinerary
                                            │
                                       Present → Formatted Response + END
```

## Quick Start

### 1. Install

```bash
cd the_project
pip install -r requirements.txt
```

### 2. Configure API Keys

```bash
cp .env.example .env
```

Edit `.env` and fill in:
- `GOOGLE_API_KEY` — Gemini API key (required)
- `GOOGLE_MAPS_API_KEY` — Places + Routes API key (recommended)
- `OPENWEATHERMAP_API_KEY` — Free tier weather data (recommended)
- `AVIATIONSTACK_API_KEY` — Flight data (optional)

### 3. Authenticate with Google Cloud

```bash
gcloud auth application-default login
```

### 4. Start MCP Toolbox Server

Download [GenAI Toolbox](https://github.com/googleapis/genai-toolbox/releases), then:

```bash
python start_mcp.py
```

### 5. Run the CLI Agent

```bash
python -m agent.cli
```

### 6. Run the API Server (for frontend)

```bash
uvicorn backend.main:app --reload --port 8000
```

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | Health check |
| POST | `/plan` | Plan a trip (sync, full result) |
| POST | `/plan/stream` | Plan a trip (SSE streaming events) |
| GET | `/itinerary/{id}` | Retrieve saved itinerary |

## Project Structure

```
the_project/
├── agent/                    # LangGraph multi-agent system
│   ├── agents/               # A2A agent personas
│   │   ├── orchestrator.py   # User-facing intent extraction
│   │   ├── planner.py        # Itinerary construction + optimization
│   │   └── data_fetcher.py   # MCP tool calling (all external APIs)
│   ├── config.py             # Pydantic settings (.env)
│   ├── state.py              # AgentState with travel fields
│   ├── itinerary.py          # Structured itinerary Pydantic models
│   ├── prompts.py            # 4 agent system prompts
│   ├── guardrails.py         # CaMeL security + query validation
│   ├── tools.py              # MCP tool loader
│   ├── nodes.py              # Graph nodes + routing functions
│   ├── graph.py              # LangGraph construction
│   └── cli.py                # Interactive CLI
├── backend/                  # FastAPI server
│   └── main.py               # REST + SSE endpoints
├── frontend/                 # React 3D globe (Phase 2)
├── mcp_server/               # MCP Toolbox config
│   └── tools.yaml            # 7 travel tools
├── start_mcp.py              # MCP server launcher
├── .env.example
├── requirements.txt
├── pyproject.toml
└── Dockerfile
```

## Security (CaMeL Architecture)

1. **Static Pre-Screen** (`guardrails.py`): Regex-based injection detection
2. **LLM Verifier** (`verifier_node`): Semantic intent analysis against threat model
3. **Query Guardrails** (`guardrails.py`): DML blocking, SELECT* prevention, auto-LIMIT, dry-run cost cap
