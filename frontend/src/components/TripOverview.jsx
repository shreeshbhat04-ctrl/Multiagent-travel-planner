import { countWaypoints, formatDateRange, summarizeTools } from "../lib/formatters";

export default function TripOverview({ itinerary, events }) {
  if (!itinerary) {
    return (
      <section className="panel panel-hero">
        <p className="eyebrow">Trip output</p>
        <h2>Structured itinerary will land here.</h2>
        <p className="supporting-text">
          The planner returns a typed itinerary with flights, hotels, day plans, weather notes, and travel tips.
        </p>
      </section>
    );
  }

  const toolNames = summarizeTools(events);

  return (
    <section className="panel panel-hero">
      <div className="hero-grid">
        <div>
          <p className="eyebrow">Trip output</p>
          <h2>{itinerary.title}</h2>
          <p className="supporting-text">{itinerary.summary || "The planner completed without a summary."}</p>
        </div>
        <div className="stat-grid">
          <div className="stat-card">
            <span>Route</span>
            <strong>
              {itinerary.origin?.city || "Origin"} to {itinerary.destination?.city || "Destination"}
            </strong>
          </div>
          <div className="stat-card">
            <span>Dates</span>
            <strong>{formatDateRange(itinerary.start_date, itinerary.end_date)}</strong>
          </div>
          <div className="stat-card">
            <span>Travelers</span>
            <strong>{itinerary.num_travelers || 1}</strong>
          </div>
          <div className="stat-card">
            <span>Stops</span>
            <strong>{countWaypoints(itinerary)}</strong>
          </div>
          <div className="stat-card">
            <span>Budget</span>
            <strong>{itinerary.budget_level || "TBD"}</strong>
          </div>
          <div className="stat-card">
            <span>Estimated cost</span>
            <strong>{itinerary.total_estimated_cost || "Pending"}</strong>
          </div>
        </div>
      </div>

      {toolNames.length ? (
        <div className="tag-row">
          {toolNames.map((tool) => (
            <span className="tool-chip" key={tool}>
              {tool}
            </span>
          ))}
        </div>
      ) : null}
    </section>
  );
}
