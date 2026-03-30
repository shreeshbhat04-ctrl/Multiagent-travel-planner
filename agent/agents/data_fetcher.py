"""Data Fetcher Agent — all external data ingestion via MCP tools.

This agent is the ONLY one that interacts with external APIs.
It receives structured requests from the Planner and returns raw data context.
Exposed as an A2A Server: receives requests, calls MCP tools, returns results.
"""

import json
import logging
from typing import Dict

from langchain_core.messages import AIMessage, SystemMessage, HumanMessage
from langchain_google_genai import ChatGoogleGenerativeAI

from ..config import config
from ..prompts import DATA_FETCHER_PROMPT
from ..tools import get_tools

logger = logging.getLogger(__name__)


def _get_data_fetcher_llm():
    """Get LLM with tools bound for the data fetcher."""
    llm = ChatGoogleGenerativeAI(
        model=config.gemini_model,
        api_key=config.google_api_key,
        temperature=0,
    )
    tools = get_tools()
    if tools:
        llm = llm.bind_tools(tools)
    return llm


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

    llm = _get_data_fetcher_llm()
    response = llm.invoke(messages)
    response.name = "DataFetcher"

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

    # Scan messages for tool results
    for msg in state.get("messages", []):
        content = getattr(msg, "content", "")
        if not isinstance(content, str):
            continue

        try:
            data = json.loads(content)

            # Detect data type from content
            if isinstance(data, dict):
                if "places" in data or "results" in data:
                    raw_places = data.get("places", data.get("results", []))
                    if isinstance(raw_places, list):
                        places_data.extend(raw_places)
                elif "forecast" in data or "weather" in data or "temperature" in data:
                    weather_data = data
                elif "flights" in data:
                    flight_data = data.get("flights", [])
            elif isinstance(data, list):
                # Could be places or flights
                if data and isinstance(data[0], dict):
                    if "place_id" in data[0] or "name" in data[0]:
                        places_data.extend(data)
                    elif "flight_number" in data[0] or "airline" in data[0]:
                        flight_data.extend(data)

        except (json.JSONDecodeError, TypeError, IndexError):
            continue

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
