"""Data Fetcher Agent — all external data ingestion via MCP tools.

This agent is the ONLY one that interacts with external APIs.
It receives structured requests from the Planner and returns raw data context.
Exposed as an A2A Server: receives requests, calls MCP tools, returns results.
"""

import json
import logging
import uuid
from typing import Dict, Optional

from langchain_core.messages import AIMessage, SystemMessage, HumanMessage
from langchain_google_genai import ChatGoogleGenerativeAI

from ..config import config
from ..prompts import DATA_FETCHER_PROMPT
from ..tools import get_data_fetcher_tools

logger = logging.getLogger(__name__)

FALLBACK_AIRPORT_LOOKUP = {
    "bali": "DPS",
    "bangalore": "BLR",
    "bangaluru": "BLR",
    "bengaluru": "BLR",
    "bangkok": "BKK",
    "delhi": "DEL",
    "dubai": "DXB",
    "goa": "GOI",
    "istanbul": "IST",
    "london": "LHR",
    "mumbai": "BOM",
    "new york": "JFK",
    "paris": "CDG",
    "singapore": "SIN",
    "tokyo": "NRT",
}


def _content_to_text(content) -> str:
    """Flatten message/tool content blocks into plain text when possible."""
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


def _normalize_flight_record(record: object) -> Optional[dict]:
    """Normalize provider-specific flight payloads into planner-friendly fields."""
    if not isinstance(record, dict):
        return None

    airline_obj = record.get("airline", {})
    flight_obj = record.get("flight", {})
    departure_obj = record.get("departure", {})
    arrival_obj = record.get("arrival", {})

    if isinstance(airline_obj, dict) or isinstance(flight_obj, dict) or isinstance(departure_obj, dict) or isinstance(arrival_obj, dict):
        airline_name = airline_obj.get("name") if isinstance(airline_obj, dict) else airline_obj
        return {
            "airline": airline_name or record.get("airline_name") or "Unknown airline",
            "flight_number": (
                flight_obj.get("number") if isinstance(flight_obj, dict) else None
            ) or record.get("flight_number"),
            "departure_airport": (
                departure_obj.get("iata") if isinstance(departure_obj, dict) else None
            ) or record.get("dep_iata") or record.get("departure_airport") or "TBD",
            "arrival_airport": (
                arrival_obj.get("iata") if isinstance(arrival_obj, dict) else None
            ) or record.get("arr_iata") or record.get("arrival_airport") or "TBD",
            "departure_time": (
                departure_obj.get("scheduled") if isinstance(departure_obj, dict) else None
            ) or (
                departure_obj.get("estimated") if isinstance(departure_obj, dict) else None
            ) or record.get("departure_time") or "TBD",
            "arrival_time": (
                arrival_obj.get("scheduled") if isinstance(arrival_obj, dict) else None
            ) or (
                arrival_obj.get("estimated") if isinstance(arrival_obj, dict) else None
            ) or record.get("arrival_time") or "TBD",
            "duration": record.get("duration") or record.get("flight_time"),
            "price_estimate": record.get("price_estimate") or record.get("cost_estimate"),
            "booking_class": record.get("booking_class"),
        }

    return record


def _merge_fetched_payload(payload: object, places_data: list, weather_data: dict, flight_data: list) -> None:
    """Merge a fetched-data payload into the processor accumulators."""
    if not payload:
        return

    if isinstance(payload, list):
        text_payload = _content_to_text(payload)
        if text_payload:
            payload = text_payload

    if isinstance(payload, str):
        try:
            payload = json.loads(payload)
        except json.JSONDecodeError:
            return

    if isinstance(payload, dict):
        for nested_key in ("data", "result", "body", "response", "content", "payload"):
            nested_payload = payload.get(nested_key)
            if nested_payload and nested_payload is not payload:
                _merge_fetched_payload(nested_payload, places_data, weather_data, flight_data)

        places = payload.get("places") or payload.get("results")
        if isinstance(places, list):
            places_data.extend(place for place in places if isinstance(place, dict))

        weather = (
            payload.get("weather")
            or payload.get("weather_data")
            or payload.get("forecast")
        )
        if isinstance(weather, dict):
            weather_data.update(weather)
        elif any(key in payload for key in ("forecast", "weather", "temperature")):
            weather_data.update(payload)

        flights = payload.get("flights") or payload.get("flight_data")
        if isinstance(flights, list):
            for flight in flights:
                normalized = _normalize_flight_record(flight)
                if normalized:
                    flight_data.append(normalized)

    elif isinstance(payload, list) and payload and isinstance(payload[0], dict):
        if (
            "flight_number" in payload[0]
            or "airline" in payload[0]
            or "flight" in payload[0]
            or "departure" in payload[0]
            or "arrival" in payload[0]
        ):
            for flight in payload:
                normalized = _normalize_flight_record(flight)
                if normalized:
                    flight_data.append(normalized)
        else:
            places_data.extend(payload)


def _get_data_fetcher_llm():
    """Get LLM with tools bound for the data fetcher."""
    llm = ChatGoogleGenerativeAI(
        model=config.gemini_model,
        api_key=config.google_api_key,
        temperature=0,
    )
    tools = get_data_fetcher_tools()
    if tools:
        llm = llm.bind_tools(tools)
    return llm


def _tool_messages(state: Dict) -> list:
    """Return tool messages from the conversation state."""
    return [msg for msg in state.get("messages", []) if getattr(msg, "type", "") == "tool"]


def _tool_name_from_message(msg) -> str:
    """Best-effort extraction of a tool message's tool name."""
    return getattr(msg, "name", "") or getattr(msg, "tool_name", "")


def _expected_tool_names(travel_params: dict) -> set[str]:
    """Determine which travel tools should run for the current request."""
    expected = {"destination-lookup", "search-places", "get-weather"}
    if travel_params.get("start_date") and travel_params.get("start_date") != "flexible":
        expected.add("seasonal-insights")
    if travel_params.get("origin") and travel_params.get("origin") not in {"", "not specified"}:
        expected.add("airport-lookup")
        expected.add("search-flights")
    return expected


def _tool_call_requested(state: Dict, tool_name: str, **expected_args) -> bool:
    """Return whether a specific tool call with matching args already exists."""
    for msg in state.get("messages", []):
        for tool_call in getattr(msg, "tool_calls", []) or []:
            if tool_call.get("name") != tool_name:
                continue
            args = tool_call.get("args", {})
            if not isinstance(args, dict):
                continue
            if all(str(args.get(key, "")).strip().lower() == str(value).strip().lower() for key, value in expected_args.items()):
                return True
    return False


def _parse_payload(value: object) -> object:
    """Parse JSON strings while leaving structured values untouched."""
    if isinstance(value, str):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return value
    return value


def _fallback_iata_for_city(city: str) -> Optional[str]:
    """Return a local fallback IATA code for common cities."""
    if not city:
        return None
    return FALLBACK_AIRPORT_LOOKUP.get(city.strip().lower())


def _find_iata_code(payload: object, city: str) -> Optional[str]:
    """Recursively search a payload for an IATA code matching the given city."""
    payload = _parse_payload(payload)

    if isinstance(payload, list):
        for item in payload:
            code = _find_iata_code(item, city)
            if code:
                return code
        return None

    if not isinstance(payload, dict):
        return None

    candidate_city = payload.get("city") or payload.get("destination") or payload.get("origin")
    candidate_iata = payload.get("iata_code") or payload.get("iata")
    if candidate_iata and (not city or str(candidate_city).strip().lower() == city.strip().lower()):
        return str(candidate_iata)

    for key in ("data", "result", "body", "response", "content", "payload", "results"):
        nested = payload.get(key)
        if nested is not None:
            code = _find_iata_code(nested, city)
            if code:
                return code

    for nested in payload.values():
        code = _find_iata_code(nested, city)
        if code:
            return code

    return None


def _extract_iata_from_state(state: Dict, city: str) -> Optional[str]:
    """Look for an airport IATA code for a city in prior tool outputs."""
    for msg in state.get("messages", []):
        if getattr(msg, "type", "") != "tool":
            continue
        tool_name = _tool_name_from_message(msg)
        if tool_name not in {"destination-lookup", "airport-lookup"}:
            continue
        code = _find_iata_code(getattr(msg, "content", ""), city)
        if code:
            return code
    return _fallback_iata_for_city(city)


def _build_search_flights_tool_call(state: Dict, travel_params: dict) -> Optional[AIMessage]:
    """Build a deterministic search-flights tool call when enough data is known."""
    origin = travel_params.get("origin", "")
    destination = travel_params.get("destination", "")
    if not origin or origin == "not specified" or not destination:
        return None

    if not config.aviationstack_api_key:
        logger.warning("Skipping flight search because AVIATIONSTACK_API_KEY is not configured.")
        return None

    dep_iata = _extract_iata_from_state(state, origin)
    arr_iata = _extract_iata_from_state(state, destination)
    if not dep_iata or not arr_iata:
        return None

    args = {
        "access_key": config.aviationstack_api_key,
        "dep_iata": dep_iata,
        "arr_iata": arr_iata,
        "limit": "8",
    }
    start_date = travel_params.get("start_date")
    if start_date and start_date != "flexible":
        args["flight_date"] = start_date

    return AIMessage(
        content=f"Searching flights from {dep_iata} to {arr_iata}.",
        name="DataFetcher",
        tool_calls=[{
            "name": "search-flights",
            "args": args,
            "id": f"search_flights_{uuid.uuid4().hex[:8]}",
            "type": "tool_call",
        }],
    )


def _build_data_summary(state: Dict) -> dict:
    """Aggregate currently available travel data from the message history."""
    places_data = []
    weather_data = {}
    flight_data = []

    for msg in state.get("messages", []):
        content = _content_to_text(getattr(msg, "content", ""))
        if getattr(msg, "type", "") == "tool":
            logger.info(
                "Tool message observed: name=%s content_snippet=%s",
                _tool_name_from_message(msg),
                content[:300] if content else "",
            )
        if content:
            _merge_fetched_payload(content, places_data, weather_data, flight_data)

        tool_calls = getattr(msg, "tool_calls", []) or []
        for tool_call in tool_calls:
            if tool_call.get("name") != "SubmitFetchedData":
                continue
            args = tool_call.get("args", {})
            if isinstance(args, dict):
                _merge_fetched_payload(
                    args.get("data_summary"),
                    places_data,
                    weather_data,
                    flight_data,
                )

    return {
        "places": places_data,
        "weather": weather_data,
        "flights": flight_data,
    }


def _should_finalize_data_fetch(state: Dict, travel_params: dict) -> bool:
    """Stop the fetch loop once expected tools ran or recursion is likely."""
    tool_messages = _tool_messages(state)
    executed = {_tool_name_from_message(msg) for msg in tool_messages if _tool_name_from_message(msg)}
    expected = _expected_tool_names(travel_params)

    if expected and expected.issubset(executed):
        logger.info("Data Fetcher has collected all expected tool outputs: %s", sorted(executed))
        return True

    if len(tool_messages) >= max(4, len(expected) + 1):
        logger.info(
            "Data Fetcher reached tool-loop cutoff with executed tools: %s",
            sorted(executed),
        )
        return True

    return False


def data_fetcher_node(state: Dict) -> Dict:
    """Data Fetcher: Calls MCP tools to gather travel data.

    Uses travel_params to determine what data to fetch:
    - Places near destination (via search-places)
    - Weather forecast (via get-weather)
    - Flight options (via search-flights)
    - BigQuery analytics (via execute-query)
    """
    logger.info("Data Fetcher gathering travel data...")

    travel_params = state.get("travel_params", {})
    destination = travel_params.get("destination", "")
    origin = travel_params.get("origin", "")

    # Check if this is the first time Data Fetcher is running
    is_first_turn = True
    for msg in reversed(state.get("messages", [])):
        if getattr(msg, "name", "") == "DataFetcher" or getattr(msg, "type", "") == "tool":
            is_first_turn = False
            break

    messages = [SystemMessage(content=DATA_FETCHER_PROMPT)] + state.get("messages", [])

    if is_first_turn:
        logger.info("Data Fetcher starting new data collection...")
        fetch_instructions = _build_fetch_request(travel_params)
        messages.append(HumanMessage(content=fetch_instructions))
    else:
        logger.info("Data Fetcher continuing tool execution loop...")
        if origin and origin not in {"", "not specified"}:
            if not _tool_call_requested(state, "airport-lookup", city=origin) and not _extract_iata_from_state(state, origin):
                return {
                    "messages": [AIMessage(
                        content=f"Resolving the primary airport for {origin}.",
                        name="DataFetcher",
                        tool_calls=[{
                            "name": "airport-lookup",
                            "args": {"city": origin},
                            "id": f"airport_lookup_origin_{uuid.uuid4().hex[:8]}",
                            "type": "tool_call",
                        }],
                    )],
                    "sender": "DataFetcher",
                }

            if not _tool_call_requested(state, "airport-lookup", city=destination) and not _extract_iata_from_state(state, destination):
                return {
                    "messages": [AIMessage(
                        content=f"Resolving the primary airport for {destination}.",
                        name="DataFetcher",
                        tool_calls=[{
                            "name": "airport-lookup",
                            "args": {"city": destination},
                            "id": f"airport_lookup_destination_{uuid.uuid4().hex[:8]}",
                            "type": "tool_call",
                        }],
                    )],
                    "sender": "DataFetcher",
                }

            if not _tool_call_requested(state, "search-flights"):
                flight_tool_call = _build_search_flights_tool_call(state, travel_params)
                if flight_tool_call is not None:
                    return {
                        "messages": [flight_tool_call],
                        "sender": "DataFetcher",
                    }

        if _should_finalize_data_fetch(state, travel_params):
            summary = _build_data_summary(state)
            return {
                "messages": [AIMessage(
                    content="Submitting gathered travel data to the planner.",
                    name="DataFetcher",
                    tool_calls=[{
                        "name": "SubmitFetchedData",
                        "args": {"data_summary": json.dumps(summary)},
                        "id": f"submit_fetched_data_{uuid.uuid4().hex[:8]}",
                        "type": "tool_call",
                    }],
                )],
                "sender": "DataFetcher",
            }

    llm = _get_data_fetcher_llm()
    response = llm.invoke(messages)
    response.name = "DataFetcher"
    if getattr(response, "tool_calls", None):
        logger.info(
            "Data Fetcher proposed tool calls: %s",
            [tc.get("name", "") for tc in response.tool_calls],
        )

    return {
        "messages": [response],
        "sender": "DataFetcher",
    }


def _build_fetch_request(travel_params: dict) -> str:
    """Build a comprehensive data fetching request from travel params."""
    dest = travel_params.get("destination", "Unknown destination")
    origin = travel_params.get("origin", "")
    start_date = travel_params.get("start_date", "")
    end_date = travel_params.get("end_date", "")
    num_days = travel_params.get("num_days", 3)
    interests = travel_params.get("interests", [])
    budget = travel_params.get("budget_level", "mid-range")

    step = 1
    parts = [
        f"Gather comprehensive travel data for a trip to {dest}.",
        "",
        "Please call the following tools IN ORDER:",
        "",
        f"{step}. **destination-lookup**: Look up destination intelligence for {dest}.",
        f"   This returns cost index, safety score, visa requirements, daily budget,",
        f"   best months, IATA code, and currency from our BigQuery travel database.",
    ]
    step += 1

    if origin and origin not in {"", "not specified"}:
        parts.append("")
        parts.append(f"{step}. **airport-lookup**: Resolve the primary airport for {origin}.")
        parts.append("   Use this to obtain the origin IATA code before flight search.")
        step += 1

    if start_date:
        # Extract month from start_date (YYYY-MM-DD)
        try:
            month = str(int(start_date.split("-")[1]))
        except (IndexError, ValueError):
            month = "1"
        parts.append("")
        parts.append(f"{step}. **seasonal-insights**: Get seasonal conditions for {dest} in month {month}.")
        parts.append(f"   Returns temperature, rainfall, crowd level, and whether it's recommended.")
        step += 1

    parts.append("")
    parts.append(f"{step}. **search-places**: Search for top attractions and points of interest in {dest}.")
    parts.append(f"   Focus on: {', '.join(interests) if interests else 'popular attractions, restaurants, cultural sites'}")
    step += 1

    parts.append("")
    parts.append(f"{step}. **get-weather**: Get the weather forecast for {dest}.")
    step += 1

    if start_date:
        parts.append(f"   Dates: {start_date} to {end_date or 'flexible'}")

    if origin:
        parts.append("")
        parts.append(f"{step}. **search-flights**: Find flights from {origin} to {dest}.")
        parts.append("   Use IATA codes from destination-lookup / airport-lookup for dep_iata and arr_iata.")
        if start_date:
            parts.append(f"   Departure: {start_date}, Return: {end_date or 'flexible'}")
        step += 1

    parts.append("")
    parts.append(
        f"Budget level: {budget}. "
        f"Trip duration: {num_days} days. "
        "After calling all tools, compile ALL results into a structured data summary."
    )
    parts.append("")
    parts.append(
        "IMPORTANT: Include the BigQuery destination intelligence data (cost_index, "
        "visa_required, avg_daily_budget_usd, safety_score, best_months, currency) "
        "in your SubmitFetchedData call — the Planner uses this for budget estimates."
    )
    if origin and origin not in {"", "not specified"}:
        parts.append("IMPORTANT: Do not call `SubmitFetchedData` until you have attempted `search-flights`.")
    parts.append("")
    parts.append("Call `SubmitFetchedData` with ALL the gathered data as a JSON string.")

    return "\n".join(parts)


def process_fetched_data(state: Dict) -> Dict:
    """Process raw tool results into structured data for the Planner.

    Extracts places, weather, and flight data from the message history
    and stores them in state for the Planner to consume.
    """
    logger.info("Processing fetched data for Planner...")

    places_data = []
    weather_data = {}
    flight_data = []

    # Scan messages for tool results and SubmitFetchedData payloads
    for msg in state.get("messages", []):
        content = _content_to_text(getattr(msg, "content", ""))
        if content:
            _merge_fetched_payload(content, places_data, weather_data, flight_data)

        tool_calls = getattr(msg, "tool_calls", []) or []
        for tool_call in tool_calls:
            if tool_call.get("name") != "SubmitFetchedData":
                continue
            args = tool_call.get("args", {})
            if isinstance(args, dict):
                _merge_fetched_payload(
                    args.get("data_summary"),
                    places_data,
                    weather_data,
                    flight_data,
                )

    logger.info(
        "Fetched data summary: %d places, weather=%s, %d flights",
        len(places_data),
        bool(weather_data),
        len(flight_data),
    )

    return {
        "places_data": places_data if places_data else None,
        "weather_data": weather_data if weather_data else None,
        "flight_data": flight_data if flight_data else None,
        "sender": "DataProcessor",
    }
