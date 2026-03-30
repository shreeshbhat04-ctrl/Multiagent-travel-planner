export function formatDateRange(startDate, endDate) {
  if (!startDate && !endDate) {
    return "Dates to be confirmed";
  }

  const formatter = new Intl.DateTimeFormat("en", {
    month: "short",
    day: "numeric",
    year: "numeric"
  });

  const start = startDate ? formatter.format(new Date(startDate)) : "TBD";
  const end = endDate ? formatter.format(new Date(endDate)) : "TBD";
  return `${start} - ${end}`;
}

export function formatNodeName(node) {
  return (node || "system")
    .replace(/_/g, " ")
    .replace(/\b\w/g, (match) => match.toUpperCase());
}

export function buildTripStops(itinerary, activeDayIndex) {
  if (!itinerary) {
    return [];
  }

  const stops = [];

  if (itinerary.origin?.lat !== undefined && itinerary.origin?.lng !== undefined) {
    stops.push({
      id: "origin",
      kind: "origin",
      label: itinerary.origin.city || "Origin",
      lat: itinerary.origin.lat,
      lng: itinerary.origin.lng,
      subtitle: itinerary.origin.country || "",
      dayNumber: 0
    });
  }

  const days = Array.isArray(itinerary.days) ? itinerary.days : [];
  const visibleDays =
    typeof activeDayIndex === "number" ? days.filter((_, index) => index === activeDayIndex) : days;

  visibleDays.forEach((day) => {
    day.waypoints?.forEach((waypoint, waypointIndex) => {
      if (typeof waypoint.lat !== "number" || typeof waypoint.lng !== "number") {
        return;
      }

      stops.push({
        id: `${day.day_number}-${waypointIndex}`,
        kind: waypoint.category || "waypoint",
        label: waypoint.name,
        lat: waypoint.lat,
        lng: waypoint.lng,
        subtitle: waypoint.description || day.title || "",
        dayNumber: day.day_number
      });
    });
  });

  if (itinerary.destination?.lat !== undefined && itinerary.destination?.lng !== undefined) {
    stops.push({
      id: "destination",
      kind: "destination",
      label: itinerary.destination.city || "Destination",
      lat: itinerary.destination.lat,
      lng: itinerary.destination.lng,
      subtitle: itinerary.destination.country || "",
      dayNumber: days.length + 1
    });
  }

  return stops;
}

export function countWaypoints(itinerary) {
  if (!itinerary?.days) {
    return 0;
  }

  return itinerary.days.reduce((total, day) => total + (day.waypoints?.length || 0), 0);
}

export function summarizeTools(events) {
  const tools = new Set();

  events.forEach((event) => {
    event.tool_calls?.forEach((tool) => {
      if (tool.name) {
        tools.add(tool.name);
      }
    });
  });

  return Array.from(tools);
}
