"""Structured itinerary models — canonical Pydantic output schema.

The Planner Agent is forced to produce output matching these models.
The frontend uses this JSON structure to render the 3D globe experience.
"""

from typing import Optional
from pydantic import BaseModel, Field


class GeoPoint(BaseModel):
    """Geographic coordinate."""
    lat: float = Field(..., description="Latitude")
    lng: float = Field(..., description="Longitude")


class Location(BaseModel):
    """A named location with coordinates."""
    city: str
    country: str
    lat: float
    lng: float
    iata: Optional[str] = Field(None, description="Airport IATA code if applicable")


class Waypoint(BaseModel):
    """A single stop in the daily itinerary."""
    name: str = Field(..., description="Name of the place/activity")
    description: str = Field("", description="Brief description of what to do")
    lat: float
    lng: float
    place_id: Optional[str] = Field(None, description="Google Maps place_id")
    category: str = Field("attraction", description="attraction|restaurant|hotel|transport|activity")
    start_time: Optional[str] = Field(None, description="Suggested start time, e.g. '09:00'")
    duration_min: int = Field(60, description="Estimated duration in minutes")
    cost_estimate: Optional[str] = Field(None, description="Estimated cost, e.g. '$25' or 'Free'")
    rating: Optional[float] = Field(None, description="Google Maps rating 1-5")
    notes: Optional[str] = Field(None, description="Tips, reviews summary, or weather advisory")


class DayPlan(BaseModel):
    """Plan for a single day of the trip."""
    day_number: int
    date: Optional[str] = Field(None, description="ISO date YYYY-MM-DD")
    title: str = Field(..., description="Theme for the day, e.g. 'Exploring Shibuya & Harajuku'")
    summary: str = Field("", description="Brief narrative of the day's plan")
    waypoints: list[Waypoint] = Field(default_factory=list)
    weather_forecast: Optional[str] = Field(None, description="Expected weather for this day")


class FlightInfo(BaseModel):
    """Flight details."""
    airline: str
    flight_number: Optional[str] = None
    departure_airport: str = Field(..., description="IATA code")
    arrival_airport: str = Field(..., description="IATA code")
    departure_time: str
    arrival_time: str
    duration: Optional[str] = None
    price_estimate: Optional[str] = None
    booking_class: Optional[str] = None


class HotelInfo(BaseModel):
    """Hotel/accommodation details."""
    name: str
    lat: float
    lng: float
    place_id: Optional[str] = None
    rating: Optional[float] = None
    price_per_night: Optional[str] = None
    check_in: Optional[str] = None
    check_out: Optional[str] = None
    notes: Optional[str] = None


class TravelItinerary(BaseModel):
    """Complete structured travel itinerary — the canonical output of the Planner Agent.

    This JSON structure drives both the frontend 3D globe rendering
    and the textual itinerary display.
    """
    title: str = Field(..., description="Trip title, e.g. '5-Day Tokyo Adventure'")
    origin: Location
    destination: Location
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    num_travelers: int = 1
    budget_level: str = "mid-range"
    summary: str = Field("", description="Executive summary of the trip")
    days: list[DayPlan] = Field(default_factory=list)
    flights: list[FlightInfo] = Field(default_factory=list)
    hotels: list[HotelInfo] = Field(default_factory=list)
    total_estimated_cost: Optional[str] = None
    travel_tips: list[str] = Field(default_factory=list)
