export default function LogisticsPanel({ itinerary }) {
  const flights = itinerary?.flights || [];
  const hotels = itinerary?.hotels || [];
  const tips = itinerary?.travel_tips || [];

  return (
    <section className="panel">
      <div className="panel-heading">
        <div>
          <p className="eyebrow">Logistics</p>
          <h2>Flights, stays, and travel notes</h2>
        </div>
      </div>

      <div className="logistics-grid">
        <div className="logistics-column">
          <h3>Flights</h3>
          {flights.length ? (
            flights.map((flight, index) => (
              <article key={`${flight.airline}-${index}`} className="logistics-card">
                <strong>
                  {flight.airline} {flight.flight_number || ""}
                </strong>
                <p>
                  {flight.departure_airport} to {flight.arrival_airport}
                </p>
                <small>
                  {flight.departure_time} to {flight.arrival_time}
                </small>
                <small>{flight.price_estimate || "Price pending"}</small>
              </article>
            ))
          ) : (
            <p className="muted-text">No flight options were returned.</p>
          )}
        </div>

        <div className="logistics-column">
          <h3>Hotels</h3>
          {hotels.length ? (
            hotels.map((hotel, index) => (
              <article key={`${hotel.name}-${index}`} className="logistics-card">
                <strong>{hotel.name}</strong>
                <p>{hotel.price_per_night || "Price pending"}</p>
                <small>{hotel.rating ? `Rating ${hotel.rating}` : "Rating unavailable"}</small>
                <small>{hotel.notes || "No extra notes."}</small>
              </article>
            ))
          ) : (
            <p className="muted-text">No hotel recommendations were returned.</p>
          )}
        </div>

        <div className="logistics-column">
          <h3>Travel tips</h3>
          {tips.length ? (
            <ul className="tip-list">
              {tips.map((tip, index) => (
                <li key={`${tip}-${index}`}>{tip}</li>
              ))}
            </ul>
          ) : (
            <p className="muted-text">No travel tips were returned.</p>
          )}
        </div>
      </div>
    </section>
  );
}
