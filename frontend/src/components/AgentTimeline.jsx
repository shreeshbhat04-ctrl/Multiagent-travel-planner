import { formatNodeName } from "../lib/formatters";

function eventTone(node) {
  if (node === "error") return "tone-danger";
  if (node === "planner" || node === "present") return "tone-success";
  if (node === "execute_tools" || node === "data_fetcher") return "tone-info";
  return "tone-neutral";
}

export default function AgentTimeline({ events, status }) {
  return (
    <section className="panel">
      <div className="panel-heading">
        <div>
          <p className="eyebrow">Agent stream</p>
          <h2>Live workflow trace</h2>
        </div>
        <span className="caption">{status}</span>
      </div>

      {events.length === 0 ? (
        <div className="empty-state compact-empty">
          <p>No events yet. Start a plan to see verifier, orchestrator, data fetcher, and planner activity.</p>
        </div>
      ) : (
        <div className="timeline">
          {events.map((event, index) => (
            <article key={`${event.node}-${index}-${event.content.slice(0, 24)}`} className="timeline-item">
              <div className={`timeline-badge ${eventTone(event.node)}`}>
                {formatNodeName(event.node)}
              </div>
              <div className="timeline-body">
                <div className="timeline-meta">
                  <span>{event.sender || "System"}</span>
                  {event.tool_calls?.length ? <span>{event.tool_calls.length} tool call(s)</span> : null}
                </div>
                <p>{event.content || "No content emitted."}</p>
                {event.tool_calls?.length ? (
                  <div className="tool-chip-row">
                    {event.tool_calls.map((tool, toolIndex) => (
                      <span className="tool-chip" key={`${tool.name}-${toolIndex}`}>
                        {tool.name}
                      </span>
                    ))}
                  </div>
                ) : null}
              </div>
            </article>
          ))}
        </div>
      )}
    </section>
  );
}
