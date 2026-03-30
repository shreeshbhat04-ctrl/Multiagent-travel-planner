"""LangGraph state definition for the A2A Travel Planner."""

from typing import Annotated, Optional
from typing_extensions import TypedDict

from langgraph.graph.message import AnyMessage, add_messages


class TravelParams(TypedDict, total=False):
    """Extracted travel parameters from user request."""
    origin: str
    destination: str
    start_date: str
    end_date: str
    num_days: int
    num_travelers: int
    interests: list[str]
    budget_level: str  # "budget", "mid-range", "luxury"
    special_requests: str


class AgentState(TypedDict):
    """Main state for the A2A Travel Planner workflow.

    Attributes:
        messages: Conversation history (uses add_messages reducer — appends).
        dataset_schema: Cached BQ schema JSON string (fetched once per session).
        sender: Tracks which agent last updated the state.
        travel_params: Extracted travel parameters from user intent.
        itinerary: Structured JSON itinerary produced by planner.
        places_data: Cached place details from Maps API.
        weather_data: Cached weather forecasts for destination.
        flight_data: Cached flight search results.
        hotel_data: Cached hotel search results.
    """

    messages: Annotated[list[AnyMessage], add_messages]
    dataset_schema: Optional[str]
    sender: str
    travel_params: Optional[TravelParams]
    itinerary: Optional[dict]
    places_data: Optional[list[dict]]
    weather_data: Optional[dict]
    flight_data: Optional[list[dict]]
    hotel_data: Optional[list[dict]]
