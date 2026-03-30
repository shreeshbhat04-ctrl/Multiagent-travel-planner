"""Orchestrator Agent — the user-facing root agent.

Interprets natural language travel requests, extracts travel parameters,
routes to planner via A2A-style delegation, and presents the final itinerary.
"""

import json
import logging
from typing import Dict

from langchain_core.messages import AIMessage, SystemMessage, HumanMessage
from langchain_google_genai import ChatGoogleGenerativeAI

from ..config import config
from ..prompts import ORCHESTRATOR_PROMPT

logger = logging.getLogger(__name__)


def _content_to_text(content) -> str:
    """Flatten Gemini/LangChain content blocks into plain text."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict):
                text = item.get("text")
                if text:
                    parts.append(text)
        return "\n".join(parts).strip()
    return str(content)


def _get_orchestrator_llm():
    """Get LLM for the orchestrator (no tools, just NL reasoning)."""
    return ChatGoogleGenerativeAI(
        model=config.gemini_model,
        api_key=config.google_api_key,
        temperature=0.3,
    )


def orchestrator_node(state: Dict) -> Dict:
    """Orchestrator: Parse user intent → extract travel params → route to planner.

    The Orchestrator handles two scenarios:
    1. Initial request: Extract travel parameters and delegate to Planner
    2. After Planner returns: Present the formatted itinerary to the user
    """
    logger.info("Orchestrator processing user request...")

    # If we already have an itinerary, format and present it
    if state.get("itinerary"):
        itinerary = state["itinerary"]
        # Format the itinerary as a rich text response
        formatted = _format_itinerary_response(itinerary)
        return {
            "messages": [AIMessage(content=formatted, name="Orchestrator")],
            "sender": "Orchestrator",
        }

    # Extract travel intent from user message
    messages = [SystemMessage(content=ORCHESTRATOR_PROMPT)] + state["messages"]

    llm = _get_orchestrator_llm()
    response = llm.invoke(messages)
    response.content = _content_to_text(response.content)
    response.name = "Orchestrator"

    # Try to parse travel parameters from the orchestrator's response
    travel_params = _extract_travel_params(response.content)

    return {
        "messages": [response],
        "sender": "Orchestrator",
        "travel_params": travel_params,
    }


def _extract_travel_params(orchestrator_response: str) -> dict:
    """Extract structured travel parameters from orchestrator's NL response.

    The orchestrator is prompted to include a JSON block with params.
    """
    try:
        # Look for JSON block in response
        if "```json" in orchestrator_response:
            json_str = orchestrator_response.split("```json")[1].split("```")[0].strip()
        elif "{" in orchestrator_response and "}" in orchestrator_response:
            # Find the first complete JSON object
            start = orchestrator_response.index("{")
            depth = 0
            end = start
            for i, c in enumerate(orchestrator_response[start:], start):
                if c == "{":
                    depth += 1
                elif c == "}":
                    depth -= 1
                    if depth == 0:
                        end = i + 1
                        break
            json_str = orchestrator_response[start:end]
        else:
            return {}

        params = json.loads(json_str)
        logger.info("Extracted travel params: %s", params)
        return params
    except (json.JSONDecodeError, ValueError, IndexError):
        logger.warning("Could not extract travel params from orchestrator response")
        return {}


def _format_itinerary_response(itinerary: dict) -> str:
    """Format the structured itinerary into a rich text response."""
    parts = []
    title = itinerary.get("title", "Your Travel Itinerary")
    parts.append(f"# ✈️ {title}\n")

    summary = itinerary.get("summary", "")
    if summary:
        parts.append(f"{summary}\n")

    # Origin → Destination
    origin = itinerary.get("origin", {})
    dest = itinerary.get("destination", {})
    if origin and dest:
        parts.append(f"📍 **{origin.get('city', 'Origin')}** → **{dest.get('city', 'Destination')}**\n")

    # Flights
    flights = itinerary.get("flights", [])
    if flights:
        parts.append("## ✈️ Flights\n")
        for f in flights:
            parts.append(
                f"- **{f.get('airline', '')} {f.get('flight_number', '')}**: "
                f"{f.get('departure_airport', '')} → {f.get('arrival_airport', '')} | "
                f"{f.get('departure_time', '')} - {f.get('arrival_time', '')} | "
                f"{f.get('price_estimate', 'TBD')}\n"
            )

    # Hotels
    hotels = itinerary.get("hotels", [])
    if hotels:
        parts.append("\n## 🏨 Hotels\n")
        for h in hotels:
            parts.append(
                f"- **{h.get('name', 'Hotel')}** | "
                f"⭐ {h.get('rating', 'N/A')} | "
                f"{h.get('price_per_night', 'TBD')}/night\n"
            )

    # Daily plans
    days = itinerary.get("days", [])
    if days:
        for day in days:
            parts.append(f"\n## 📅 Day {day.get('day_number', '?')}: {day.get('title', '')}\n")
            if day.get("weather_forecast"):
                parts.append(f"🌤️ *{day['weather_forecast']}*\n")
            if day.get("summary"):
                parts.append(f"{day['summary']}\n")
            for wp in day.get("waypoints", []):
                time_str = f" @ {wp['start_time']}" if wp.get("start_time") else ""
                cost_str = f" | {wp['cost_estimate']}" if wp.get("cost_estimate") else ""
                rating_str = f" | ⭐ {wp['rating']}" if wp.get("rating") else ""
                parts.append(
                    f"  - **{wp.get('name', '')}**{time_str} "
                    f"({wp.get('duration_min', 60)} min{cost_str}{rating_str})\n"
                )
                if wp.get("description"):
                    parts.append(f"    {wp['description']}\n")

    # Tips
    tips = itinerary.get("travel_tips", [])
    if tips:
        parts.append("\n## 💡 Travel Tips\n")
        for tip in tips:
            parts.append(f"- {tip}\n")

    # Total cost
    total = itinerary.get("total_estimated_cost")
    if total:
        parts.append(f"\n**💰 Estimated Total Cost: {total}**\n")

    return "\n".join(parts)
