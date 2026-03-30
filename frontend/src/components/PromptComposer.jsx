const SAMPLE_PROMPTS = [
  "Plan a 5 day Tokyo trip for two food lovers in mid October with a mid-range budget.",
  "I want a 3 day Paris itinerary focused on museums, cafes, and walkable neighborhoods.",
  "Create a family trip from Bengaluru to Singapore with flights, hotel, and kid-friendly stops."
];

export default function PromptComposer({
  value,
  onChange,
  onSubmit,
  onResetSession,
  disabled,
  threadId,
  apiReady
}) {
  return (
    <section className="panel panel-form">
      <div className="panel-heading">
        <div>
          <p className="eyebrow">Plan a trip</p>
          <h2>Describe the journey in plain language.</h2>
        </div>
        <span className={`status-pill ${apiReady ? "status-live" : "status-offline"}`}>
          {apiReady ? "Backend connected" : "Backend unavailable"}
        </span>
      </div>

      <form className="planner-form" onSubmit={onSubmit}>
        <label className="field-label" htmlFor="planner-request">
          Travel brief
        </label>
        <textarea
          id="planner-request"
          className="planner-textarea"
          value={value}
          onChange={(event) => onChange(event.target.value)}
          placeholder="Example: Plan a 4 day Lisbon itinerary for a solo traveler with boutique hotels, coffee stops, and a day trip."
          disabled={disabled}
          rows={7}
        />

        <div className="chip-row">
          {SAMPLE_PROMPTS.map((prompt) => (
            <button
              key={prompt}
              className="ghost-chip"
              type="button"
              disabled={disabled}
              onClick={() => onChange(prompt)}
            >
              {prompt}
            </button>
          ))}
        </div>

        <div className="form-footer">
          <div className="session-meta">
            <span className="session-label">Thread</span>
            <code>{threadId || "new session"}</code>
          </div>
          <div className="button-row">
            <button className="secondary-button" type="button" onClick={onResetSession} disabled={disabled}>
              New session
            </button>
            <button className="primary-button" type="submit" disabled={disabled || !value.trim() || !apiReady}>
              {disabled ? "Planning..." : "Build itinerary"}
            </button>
          </div>
        </div>
      </form>
    </section>
  );
}
