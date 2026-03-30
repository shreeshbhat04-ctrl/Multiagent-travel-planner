import { useEffect, useRef, useState } from "react";
import { buildTripStops } from "../lib/formatters";

const GOOGLE_MAPS_API_KEY = import.meta.env.VITE_GOOGLE_MAPS_API_KEY;
let googleMapsPromise;

function loadGoogleMaps(apiKey) {
  if (!apiKey) {
    return Promise.reject(new Error("Missing VITE_GOOGLE_MAPS_API_KEY."));
  }

  if (window.google?.maps?.importLibrary) {
    return Promise.resolve(window.google);
  }

  if (!googleMapsPromise) {
    googleMapsPromise = new Promise((resolve, reject) => {
      const script = document.createElement("script");
      script.src = `https://maps.googleapis.com/maps/api/js?key=${apiKey}&v=beta&libraries=maps3d,marker`;
      script.async = true;
      script.onerror = () => reject(new Error("Google Maps script failed to load."));
      script.onload = () => {
        if (window.google?.maps?.importLibrary) {
          resolve(window.google);
        } else {
          reject(new Error("Google Maps library is unavailable."));
        }
      };
      document.head.append(script);
    });
  }

  return googleMapsPromise;
}

function projectPoint(lat, lng) {
  const x = ((lng + 180) / 360) * 100;
  const y = ((90 - lat) / 180) * 100;
  return { x, y };
}

function FallbackGlobe({ stops, selectedStopId }) {
  if (!stops.length) {
    return (
      <div className="map-empty">
        <h3>3D map standby</h3>
        <p>Generate an itinerary to plot the route.</p>
      </div>
    );
  }

  const points = stops.map((stop) => ({ ...stop, ...projectPoint(stop.lat, stop.lng) }));
  const path = points
    .map((point, index) => `${index === 0 ? "M" : "L"} ${point.x} ${point.y}`)
    .join(" ");

  return (
    <div className="fallback-globe">
      <svg viewBox="0 0 100 100" className="fallback-globe-svg" aria-label="Trip projection">
        <defs>
          <radialGradient id="ocean" cx="50%" cy="45%" r="65%">
            <stop offset="0%" stopColor="#0f4c81" />
            <stop offset="100%" stopColor="#031523" />
          </radialGradient>
        </defs>
        <circle cx="50" cy="50" r="46" fill="url(#ocean)" />
        <ellipse cx="50" cy="50" rx="40" ry="46" fill="none" stroke="rgba(255,255,255,0.15)" strokeWidth="0.6" />
        <ellipse cx="50" cy="50" rx="25" ry="46" fill="none" stroke="rgba(255,255,255,0.08)" strokeWidth="0.5" />
        <ellipse cx="50" cy="50" rx="46" ry="20" fill="none" stroke="rgba(255,255,255,0.08)" strokeWidth="0.5" />
        <path d={path} fill="none" stroke="#f6c26b" strokeWidth="1.2" strokeLinecap="round" strokeDasharray="3 2" />
        {points.map((point) => (
          <g key={point.id}>
            <circle
              cx={point.x}
              cy={point.y}
              r={selectedStopId === point.id ? 2.8 : 1.9}
              fill={selectedStopId === point.id ? "#fff2d1" : "#ff9f43"}
              stroke="#0c1117"
              strokeWidth="0.7"
            />
          </g>
        ))}
      </svg>

      <div className="fallback-legend">
        {stops.slice(0, 6).map((stop) => (
          <div key={stop.id} className={`legend-stop ${selectedStopId === stop.id ? "legend-stop-active" : ""}`}>
            <span>{stop.kind}</span>
            <strong>{stop.label}</strong>
          </div>
        ))}
      </div>
    </div>
  );
}

export default function GlobePanel({ itinerary, activeDayIndex, selectedStopId }) {
  const containerRef = useRef(null);
  const [mapState, setMapState] = useState(GOOGLE_MAPS_API_KEY ? "loading" : "fallback");
  const stops = buildTripStops(itinerary, activeDayIndex);

  useEffect(() => {
    let cancelled = false;

    if (!itinerary || !GOOGLE_MAPS_API_KEY || !containerRef.current) {
      setMapState(GOOGLE_MAPS_API_KEY ? "idle" : "fallback");
      return undefined;
    }

    async function renderMap() {
      try {
        const google = await loadGoogleMaps(GOOGLE_MAPS_API_KEY);
        if (cancelled || !containerRef.current) {
          return;
        }

        const { Map3DElement, Marker3DElement, Polyline3DElement } = await google.maps.importLibrary("maps3d");
        if (cancelled || !containerRef.current) {
          return;
        }

        const focusStop =
          stops.find((stop) => stop.id === selectedStopId) ||
          stops.find((stop) => stop.kind === "destination") ||
          stops[0];

        const map = new Map3DElement({
          center: {
            lat: focusStop?.lat || itinerary.destination?.lat || 0,
            lng: focusStop?.lng || itinerary.destination?.lng || 0,
            altitude: 120
          },
          range: 1200000,
          tilt: 45,
          heading: 20,
          mode: "SATELLITE",
          gestureHandling: "COOPERATIVE",
          defaultLabelsDisabled: false
        });

        const path = stops.map((stop) => ({
          lat: stop.lat,
          lng: stop.lng,
          altitude: stop.id === selectedStopId ? 160 : 80
        }));

        containerRef.current.innerHTML = "";
        containerRef.current.append(map);

        if (path.length > 1) {
          const polyline = new Polyline3DElement({
            path,
            strokeColor: "#f6c26b",
            strokeWidth: 8,
            outerColor: "#fff6e3",
            outerWidth: 2,
            drawsOccludedSegments: true
          });
          map.append(polyline);
        }

        stops.forEach((stop) => {
          const marker = new Marker3DElement({
            position: { lat: stop.lat, lng: stop.lng, altitude: stop.id === selectedStopId ? 120 : 40 },
            title: stop.label
          });
          map.append(marker);
        });

        setMapState("ready");
      } catch {
        if (!cancelled) {
          setMapState("fallback");
        }
      }
    }

    setMapState("loading");
    renderMap();

    return () => {
      cancelled = true;
      if (containerRef.current) {
        containerRef.current.innerHTML = "";
      }
    };
  }, [itinerary, activeDayIndex, selectedStopId, stops]);

  return (
    <section className="panel map-panel">
      <div className="panel-heading">
        <div>
          <p className="eyebrow">Map view</p>
          <h2>Route lens</h2>
        </div>
        <span className="caption">
          {mapState === "ready"
            ? "Google Maps 3D"
            : GOOGLE_MAPS_API_KEY
              ? mapState === "loading"
                ? "Loading 3D map"
                : "Fallback projection"
              : "Set VITE_GOOGLE_MAPS_API_KEY for 3D"}
        </span>
      </div>

      <div className="map-frame">
        {mapState === "ready" ? <div ref={containerRef} className="google-map-host" /> : <FallbackGlobe stops={stops} selectedStopId={selectedStopId} />}
      </div>
    </section>
  );
}
