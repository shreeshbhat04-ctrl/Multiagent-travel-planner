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


def _get_planner_llm():
    """Get LLM for the planner (strong reasoning model)."""
    return ChatGoogleGenerativeAI(
        model=config.planner_model,
        api_key=config.google_api_key,
        temperature=0.4,
    )


def _extract_hotel_candidates(places_data: list[dict]) -> list[dict]:
    """Return hotel/lodging places already present in fetched place results."""
    candidates = []
    for place in places_data or []:
        if not isinstance(place, dict):
            continue
        types = [str(t).lower() for t in place.get("types", []) if isinstance(t, str)]
        if "lodging" in types or "hotel" in types:
            candidates.append(place)
    return candidates


def _enforce_source_backed_logistics(itinerary: dict, flight_data: list[dict], hotel_candidates: list[dict]) -> dict:
    """Remove planner-invented logistics when no live source data exists."""
    if not flight_data:
        itinerary["flights"] = []
    if not hotel_candidates:
        itinerary["hotels"] = []
    return itinerary


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
    hotel_candidates = _extract_hotel_candidates(places_data)

    # Build context for the planner
    context_parts = []
    context_parts.append(f"TRAVEL PARAMETERS:\n{json.dumps(travel_params, indent=2)}")

    if places_data:
        context_parts.append(f"\nPLACES DATA ({len(places_data)} results):\n{json.dumps(places_data[:30], indent=2)}")
    if weather_data:
        context_parts.append(f"\nWEATHER FORECAST:\n{json.dumps(weather_data, indent=2)}")
    if flight_data:
        context_parts.append(f"\nFLIGHT OPTIONS:\n{json.dumps(flight_data[:10], indent=2)}")
    else:
        context_parts.append("\nFLIGHT OPTIONS:\n[]\nNo live flights were returned. Do not invent flights.")
    if hotel_candidates:
        context_parts.append(f"\nHOTEL CANDIDATES:\n{json.dumps(hotel_candidates[:10], indent=2)}")
    else:
        context_parts.append("\nHOTEL CANDIDATES:\n[]\nNo live hotel recommendations were returned. Do not invent hotels.")

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
    itinerary = _enforce_source_backed_logistics(itinerary, flight_data, hotel_candidates)

    return {
        "messages": [AIMessage(
            content=f"Itinerary created: {itinerary.get('title', 'Travel Plan')} — "
                    f"{len(itinerary.get('days', []))} days planned.",
            name="Planner"
        )],
        "sender": "Planner",
        "itinerary": itinerary,
    }


def _normalize_itinerary_payload(parsed: dict) -> dict:
    """Coerce near-valid model output into the canonical itinerary schema."""
    if not isinstance(parsed, dict):
        return parsed

    origin = parsed.get("origin", {}) if isinstance(parsed.get("origin"), dict) else {}
    destination = parsed.get("destination", {}) if isinstance(parsed.get("destination"), dict) else {}
    default_departure_airport = origin.get("iata") or origin.get("iata_code") or origin.get("city")
    default_arrival_airport = destination.get("iata") or destination.get("iata_code") or destination.get("city")
    destination_lat = destination.get("lat", 0)
    destination_lng = destination.get("lng", 0)

    normalized_flights = []
    for flight in parsed.get("flights", []) or []:
        if not isinstance(flight, dict):
            continue

        normalized = dict(flight)
        if normalized.get("cost_estimate") and not normalized.get("price_estimate"):
            normalized["price_estimate"] = normalized.pop("cost_estimate")

        normalized.setdefault(
            "departure_airport",
            normalized.get("dep_iata")
            or normalized.get("origin_iata")
            or normalized.get("from_airport")
            or normalized.get("from")
            or default_departure_airport
            or "TBD",
        )
        normalized.setdefault(
            "arrival_airport",
            normalized.get("arr_iata")
            or normalized.get("destination_iata")
            or normalized.get("to_airport")
            or normalized.get("to")
            or default_arrival_airport
            or "TBD",
        )
        normalized.setdefault(
            "departure_time",
            normalized.get("departure")
            or normalized.get("departure_datetime")
            or "TBD",
        )
        normalized.setdefault(
            "arrival_time",
            normalized.get("arrival")
            or normalized.get("arrival_datetime")
            or "TBD",
        )
        normalized_flights.append(normalized)

    if normalized_flights:
        parsed["flights"] = normalized_flights

    normalized_hotels = []
    for hotel in parsed.get("hotels", []) or []:
        if not isinstance(hotel, dict):
            continue

        normalized = dict(hotel)
        normalized.setdefault("lat", normalized.get("latitude", destination_lat))
        normalized.setdefault("lng", normalized.get("longitude", destination_lng))
        normalized_hotels.append(normalized)

    if normalized_hotels:
        parsed["hotels"] = normalized_hotels

    return parsed


def _parse_itinerary(response_text: str) -> dict:
    """Parse structured JSON itinerary from planner's response."""
    try:
        # Clean common markdown wrapping
        text = _content_to_text(response_text).strip()
        if text.startswith("```json"):
            text = text[len("```json"):].strip()
        if text.startswith("```"):
            text = text[len("```"):].strip()
        if text.endswith("```"):
            text = text[:-len("```")].strip()

        parsed = _normalize_itinerary_payload(json.loads(text))

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
            parsed = _normalize_itinerary_payload(json.loads(text[start:end]))
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
