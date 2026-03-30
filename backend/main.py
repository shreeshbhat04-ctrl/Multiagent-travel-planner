"""FastAPI backend for the A2A Travel Planner.

Bridges the React frontend to the LangGraph multi-agent system.
Exposes REST + SSE endpoints for trip planning.
"""

import json
import uuid
import logging
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from langchain_core.messages import HumanMessage

from agent.graph import create_agent

logging.basicConfig(level=logging.INFO, format="%(name)s | %(message)s")
logger = logging.getLogger(__name__)

app = FastAPI(
    title="A2A Travel Planner API",
    description="Multi-agent travel planning powered by LangGraph, MCP, and Gemini",
    version="1.0.0",
)

# CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Request/Response Models ──────────────────────────────

class TravelRequest(BaseModel):
    """User's travel planning request."""
    message: str = Field(..., description="Natural language travel request")
    thread_id: Optional[str] = Field(None, description="Session thread ID for multi-turn")


class TravelResponse(BaseModel):
    """Final travel planning response."""
    thread_id: str
    itinerary: Optional[dict] = None
    message: str = ""
    status: str = "completed"


class AgentEvent(BaseModel):
    """Streaming event from the agent."""
    node: str
    sender: str
    content: str
    tool_calls: list = []
    itinerary: Optional[dict] = None


# ── In-memory session store ──────────────────────────────
_sessions: dict = {}


# ── Endpoints ────────────────────────────────────────────

@app.get("/health")
async def health():
    return {"status": "healthy", "service": "a2a-travel-planner"}


@app.post("/plan", response_model=TravelResponse)
async def plan_trip(request: TravelRequest):
    """Plan a trip — synchronous endpoint (returns full result)."""
    thread_id = request.thread_id or str(uuid.uuid4())

    graph, run_config = create_agent()
    run_config["configurable"]["thread_id"] = thread_id

    try:
        result = await graph.ainvoke(
            {"messages": [HumanMessage(content=request.message)]},
            config=run_config,
        )

        itinerary = result.get("itinerary")
        last_msg = ""
        for msg in reversed(result.get("messages", [])):
            if hasattr(msg, "content") and msg.content:
                last_msg = msg.content
                break

        return TravelResponse(
            thread_id=thread_id,
            itinerary=itinerary,
            message=last_msg[:2000],
            status="completed" if itinerary else "partial",
        )

    except Exception as e:
        logger.exception("Plan trip failed")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/plan/stream")
async def plan_trip_stream(request: TravelRequest):
    """Plan a trip — streaming SSE endpoint (real-time agent events)."""
    thread_id = request.thread_id or str(uuid.uuid4())

    graph, run_config = create_agent()
    run_config["configurable"]["thread_id"] = thread_id

    async def event_stream():
        try:
            async for output in graph.astream(
                {"messages": [HumanMessage(content=request.message)]},
                config=run_config,
                stream_mode="updates",
            ):
                for node_name, node_output in output.items():
                    messages = node_output.get("messages", [])
                    sender = node_output.get("sender", "System")
                    itinerary = node_output.get("itinerary")

                    for msg in messages:
                        content = getattr(msg, "content", "")
                        if isinstance(content, list):
                            text_parts = [part.get("text", "") for part in content if isinstance(part, dict) and "text" in part]
                            content = "".join(text_parts) if text_parts else str(content)

                        tool_calls = []
                        if hasattr(msg, "tool_calls") and msg.tool_calls:
                            tool_calls = [
                                {"name": tc.get("name", ""), "args": tc.get("args", {})}
                                for tc in msg.tool_calls
                            ]

                        event = AgentEvent(
                            node=node_name,
                            sender=sender,
                            content=content[:3000],
                            tool_calls=tool_calls,
                            itinerary=itinerary,
                        )
                        yield f"data: {event.model_dump_json()}\n\n"

            yield f"data: {json.dumps({'node': 'end', 'sender': 'System', 'content': 'done', 'tool_calls': []})}\n\n"

        except Exception as e:
            logger.exception("Stream error")
            yield f"data: {json.dumps({'node': 'error', 'sender': 'System', 'content': str(e), 'tool_calls': []})}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Thread-Id": thread_id,
        },
    )


@app.get("/itinerary/{thread_id}")
async def get_itinerary(thread_id: str):
    """Retrieve a previously generated itinerary."""
    if thread_id in _sessions:
        return _sessions[thread_id]
    raise HTTPException(status_code=404, detail="Itinerary not found")
