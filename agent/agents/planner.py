"""Planner Agent — geographic logistics and itinerary construction.

Does NOT have direct access to external APIs or tools.
Instead acts as an A2A client: receives data context from the Data Fetcher
and uses it to construct optimized daily schedules.
"""

import json
import logging
from typing import Dict

from langchain_core.messages import AIMessage, SystemMessage, HumanMessage
from langchain_google_genai import ChatGoogleGenerativeAI

from ..config import config
from ..prompts import PLANNER_PROMPT
from ..itinerary import TravelItinerary

logger = logging.getLogger(__name__)


def _get_planner_llm():
    """Get LLM for the planner (strong reasoning model)."""
    return ChatGoogleGenerativeAI(
        model=config.planner_model,
        api_key=config.google_api_key,
        temperature=0.4,
    )


def planner_node(state: Dict) -> Dict:
    """Planner: Uses fetched data context to build the structured itinerary.

    Input requires: travel_params + places_data + weather_data (+ optional flight_data)
    Output: structured itinerary dict matching TravelItinerary schema
    """
    logger.info("Planner Agent constructing itinerary...")

    travel_params = state.get("travel_params", {})
    places_data = state.get("places_data", [])
    weather_data = state.get("weather_data", {})
    flight_data = state.get("flight_data", [])

    # Build context for the planner
    context_parts = []
    context_parts.append(f"TRAVEL PARAMETERS:\n{json.dumps(travel_params, indent=2)}")

    if places_data:
        context_parts.append(f"\nPLACES DATA ({len(places_data)} results):\n{json.dumps(places_data[:30], indent=2)}")
    if weather_data:
        context_parts.append(f"\nWEATHER FORECAST:\n{json.dumps(weather_data, indent=2)}")
    if flight_data:
        context_parts.append(f"\nFLIGHT OPTIONS:\n{json.dumps(flight_data[:10], indent=2)}")

    data_context = "\n".join(context_parts)

    # Build planner messages
    system_msg = SystemMessage(content=PLANNER_PROMPT)
    user_msg = HumanMessage(content=(
        f"Using the data below, create a complete travel itinerary.\n\n"
        f"{data_context}\n\n"
        f"Respond with ONLY a valid JSON object matching the TravelItinerary schema. "
        f"No markdown formatting, no explanation — just the JSON."
    ))

    llm = _get_planner_llm()
    response = llm.invoke([system_msg, user_msg])

    # Parse the itinerary from the planner's response
    itinerary = _parse_itinerary(response.content)

    return {
        "messages": [AIMessage(
            content=f"Itinerary created: {itinerary.get('title', 'Travel Plan')} — "
                    f"{len(itinerary.get('days', []))} days planned.",
            name="Planner"
        )],
        "sender": "Planner",
        "itinerary": itinerary,
    }


def _parse_itinerary(response_text: str) -> dict:
    """Parse structured JSON itinerary from planner's response."""
    try:
        # Clean common markdown wrapping
        text = response_text.strip()
        if text.startswith("```json"):
            text = text[len("```json"):].strip()
        if text.startswith("```"):
            text = text[len("```"):].strip()
        if text.endswith("```"):
            text = text[:-len("```")].strip()

        parsed = json.loads(text)

        # Validate against Pydantic schema
        itinerary = TravelItinerary(**parsed)
        return itinerary.model_dump()

    except json.JSONDecodeError as e:
        logger.error("Planner returned invalid JSON: %s", e)
        # Try to extract JSON from mixed content
        try:
            start = text.index("{")
            depth = 0
            end = start
            for i, c in enumerate(text[start:], start):
                if c == "{":
                    depth += 1
                elif c == "}":
                    depth -= 1
                    if depth == 0:
                        end = i + 1
                        break
            parsed = json.loads(text[start:end])
            itinerary = TravelItinerary(**parsed)
            return itinerary.model_dump()
        except Exception:
            pass

        return {
            "title": "Travel Plan",
            "origin": {"city": "Unknown", "country": "Unknown", "lat": 0, "lng": 0},
            "destination": {"city": "Unknown", "country": "Unknown", "lat": 0, "lng": 0},
            "summary": f"The planner encountered an error. Raw output: {response_text[:500]}",
            "days": [],
        }
    except Exception as e:
        logger.error("Planner output parsing error: %s", e)
        return {
            "title": "Travel Plan",
            "origin": {"city": "Unknown", "country": "Unknown", "lat": 0, "lng": 0},
            "destination": {"city": "Unknown", "country": "Unknown", "lat": 0, "lng": 0},
            "summary": f"Parsing error: {str(e)}",
            "days": [],
        }
