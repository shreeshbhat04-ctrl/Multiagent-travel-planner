import { useEffect, useRef, useState } from "react";
import PromptComposer from "./components/PromptComposer";
import AgentTimeline from "./components/AgentTimeline";
import TripOverview from "./components/TripOverview";
import DayPlanner from "./components/DayPlanner";
import LogisticsPanel from "./components/LogisticsPanel";
import GlobePanel from "./components/GlobePanel";
import { fetchHealth, streamPlanTrip } from "./lib/api";

const INITIAL_PROMPT =
  "Plan a 5 day trip from Bengaluru to Tokyo for two travelers with sushi, design stores, skyline views, and a mid-range budget.";

export default function App() {
  const abortRef = useRef(null);
  const itineraryRef = useRef(null);
  const [prompt, setPrompt] = useState(INITIAL_PROMPT);
  const [threadId, setThreadId] = useState("");
  const [status, setStatus] = useState("idle");
  const [events, setEvents] = useState([]);
  const [itinerary, setItinerary] = useState(null);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [apiReady, setApiReady] = useState(false);
  const [activeDayIndex, setActiveDayIndex] = useState(0);
  const [selectedStopId, setSelectedStopId] = useState("");

  useEffect(() => {
    itineraryRef.current = itinerary;
  }, [itinerary]);

  useEffect(() => {
    let mounted = true;

    fetchHealth()
      .then(() => {
        if (mounted) {
          setApiReady(true);
        }
      })
      .catch(() => {
        if (mounted) {
          setApiReady(false);
        }
      });

    return () => {
      mounted = false;
      abortRef.current?.abort();
    };
  }, []);

  useEffect(() => {
    if (!itinerary?.days?.length) {
      setActiveDayIndex(0);
      setSelectedStopId("");
      return;
    }

    setActiveDayIndex(0);
    setSelectedStopId(itinerary.days[0]?.waypoints?.length ? `${itinerary.days[0].day_number}-0` : "");
  }, [itinerary]);

  async function handleSubmit(event) {
    event.preventDefault();

    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;

    setStatus("planning");
    setError("");
    setMessage("");
    setItinerary(null);
    setEvents([]);

    try {
      await streamPlanTrip({
        message: prompt,
        threadId,
        signal: controller.signal,
        onThreadId: setThreadId,
        onEvent: (streamEvent) => {
          setEvents((current) => [...current, streamEvent]);

          if (streamEvent.content && streamEvent.node !== "end") {
            setMessage(streamEvent.content);
          }

          if (streamEvent.itinerary) {
            setItinerary(streamEvent.itinerary);
          }

          if (streamEvent.node === "error") {
            setError(streamEvent.content || "Planning failed.");
            setStatus("error");
          }

          if (streamEvent.node === "end") {
            setStatus(streamEvent.itinerary || itineraryRef.current ? "completed" : "awaiting-input");
          }
        }
      });

      setStatus((current) => (current === "error" ? current : itineraryRef.current ? "completed" : "awaiting-input"));
    } catch (requestError) {
      if (requestError.name === "AbortError") {
        return;
      }

      setError(requestError.message || "Planning request failed.");
      setStatus("error");
    }
  }

  function handleResetSession() {
    abortRef.current?.abort();
    setThreadId("");
    setEvents([]);
    setItinerary(null);
    setMessage("");
    setError("");
    setStatus("idle");
  }

  function handleSelectDay(index) {
    setActiveDayIndex(index);
    const day = itinerary?.days?.[index];
    setSelectedStopId(day?.waypoints?.length ? `${day.day_number}-0` : "");
  }

  return (
    <div className="app-shell">
      <div className="ambient ambient-one" />
      <div className="ambient ambient-two" />

      <header className="app-header">
        <div>
          <p className="eyebrow">Multi-agent travel planner</p>
          <h1>Agentic Travel Planner</h1>
        </div>
        <div className="header-meta">
          <span className={`status-pill ${apiReady ? "status-live" : "status-offline"}`}>
            {apiReady ? "API online" : "API offline"}
          </span>
          <p>
            Streaming agent trace, structured itinerary output, and a route visualization layer.
          </p>
        </div>
      </header>

      <main className="layout-grid">
        <section className="left-column">
          <PromptComposer
            value={prompt}
            onChange={setPrompt}
            onSubmit={handleSubmit}
            onResetSession={handleResetSession}
            disabled={status === "planning"}
            threadId={threadId}
            apiReady={apiReady}
          />

          {error ? (
            <section className="panel error-panel">
              <p className="eyebrow">Request status</p>
              <h2>Planning failed</h2>
              <p>{error}</p>
            </section>
          ) : null}

          {!error && message && !itinerary ? (
            <section className="panel">
              <div className="panel-heading">
                <div>
                  <p className="eyebrow">Agent response</p>
                  <h2>Latest message</h2>
                </div>
                <span className="caption">{status}</span>
              </div>
              <p className="assistant-message">{message}</p>
            </section>
          ) : null}

          <AgentTimeline events={events} status={status} />
        </section>

        <section className="right-column">
          <TripOverview itinerary={itinerary} events={events} />
          <GlobePanel itinerary={itinerary} activeDayIndex={activeDayIndex} selectedStopId={selectedStopId} />
          <DayPlanner
            itinerary={itinerary}
            activeDayIndex={activeDayIndex}
            onSelectDay={handleSelectDay}
            selectedStopId={selectedStopId}
            onSelectStop={setSelectedStopId}
          />
          <LogisticsPanel itinerary={itinerary} />
        </section>
      </main>
    </div>
  );
}
