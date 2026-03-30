export default function DayPlanner({ itinerary, activeDayIndex, onSelectDay, selectedStopId, onSelectStop }) {
  if (!itinerary?.days?.length) {
    return (
      <section className="panel">
        <div className="panel-heading">
          <div>
            <p className="eyebrow">Day by day</p>
            <h2>No daily plan yet</h2>
          </div>
        </div>
        <div className="empty-state compact-empty">
          <p>When a structured itinerary is generated, each day and waypoint will appear here.</p>
        </div>
      </section>
    );
  }

  const activeIndex = activeDayIndex ?? 0;
  const activeDay = itinerary.days[activeIndex];

  return (
    <section className="panel">
      <div className="panel-heading">
        <div>
          <p className="eyebrow">Day by day</p>
          <h2>{activeDay.title}</h2>
        </div>
        <span className="caption">{activeDay.date || "Date TBD"}</span>
      </div>

      <div className="day-tab-row">
        {itinerary.days.map((day, index) => (
          <button
            key={day.day_number}
            type="button"
            className={`day-tab ${index === activeIndex ? "day-tab-active" : ""}`}
            onClick={() => onSelectDay(index)}
          >
            <span>Day {day.day_number}</span>
            <strong>{day.title}</strong>
          </button>
        ))}
      </div>

      <div className="day-summary">
        <p>{activeDay.summary || "No narrative summary available for this day."}</p>
        {activeDay.weather_forecast ? <span className="weather-pill">{activeDay.weather_forecast}</span> : null}
      </div>

      <div className="waypoint-list">
        {activeDay.waypoints?.map((waypoint, index) => {
          const waypointId = `${activeDay.day_number}-${index}`;
          return (
            <button
              key={waypointId}
              type="button"
              className={`waypoint-card ${selectedStopId === waypointId ? "waypoint-card-active" : ""}`}
              onClick={() => onSelectStop(waypointId)}
            >
              <div className="waypoint-topline">
                <span className="waypoint-time">{waypoint.start_time || "Flexible"}</span>
                <span className="waypoint-category">{waypoint.category || "stop"}</span>
              </div>
              <h3>{waypoint.name}</h3>
              <p>{waypoint.description || "No description provided."}</p>
              <div className="waypoint-metrics">
                <span>{waypoint.duration_min || 60} min</span>
                <span>{waypoint.cost_estimate || "Cost TBD"}</span>
                <span>{waypoint.rating ? `Rating ${waypoint.rating}` : "No rating"}</span>
              </div>
              {waypoint.notes ? <small>{waypoint.notes}</small> : null}
            </button>
          );
        })}
      </div>
    </section>
  );
}
