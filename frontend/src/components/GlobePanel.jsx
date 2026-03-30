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
  const [mapNote, setMapNote] = useState("");
  const stops = buildTripStops(itinerary, activeDayIndex);
  const shouldRenderGoogleHost = Boolean(itinerary && GOOGLE_MAPS_API_KEY && mapState !== "fallback");

  useEffect(() => {
    let cancelled = false;

    if (!itinerary || !GOOGLE_MAPS_API_KEY) {
      setMapState(GOOGLE_MAPS_API_KEY ? "idle" : "fallback");
      setMapNote(GOOGLE_MAPS_API_KEY ? "" : "Missing VITE_GOOGLE_MAPS_API_KEY.");
      return undefined;
    }

    if (!containerRef.current) {
      return undefined;
    }

    async function renderMap() {
      try {
        setMapNote("");
        const google = await loadGoogleMaps(GOOGLE_MAPS_API_KEY);
        if (cancelled || !containerRef.current) {
          return;
        }

        const focusStop =
          stops.find((stop) => stop.id === selectedStopId) ||
          stops.find((stop) => stop.kind === "destination") ||
          stops[0];

        try {
          const { Map3DElement, Marker3DElement, Polyline3DElement } = await google.maps.importLibrary("maps3d");
          if (cancelled || !containerRef.current) {
            return;
          }

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

          setMapState("ready-3d");
          setMapNote("");
          return;
        } catch (threeDError) {
          console.warn("Google Maps 3D failed to initialize, switching to 2D.", threeDError);
        }

        const { Map } = await google.maps.importLibrary("maps");
        if (cancelled || !containerRef.current) {
          return;
        }

        containerRef.current.innerHTML = "";
        const map = new Map(containerRef.current, {
          center: {
            lat: focusStop?.lat || itinerary.destination?.lat || 0,
            lng: focusStop?.lng || itinerary.destination?.lng || 0
          },
          zoom: 12,
          mapTypeId: "roadmap",
          streetViewControl: false,
          mapTypeControl: false,
          fullscreenControl: false
        });

        const path = stops.map((stop) => ({ lat: stop.lat, lng: stop.lng }));
        const bounds = new google.maps.LatLngBounds();

        stops.forEach((stop) => {
          new google.maps.Marker({
            map,
            position: { lat: stop.lat, lng: stop.lng },
            title: stop.label
          });
          bounds.extend({ lat: stop.lat, lng: stop.lng });
        });

        if (path.length > 1) {
          new google.maps.Polyline({
            map,
            path,
            geodesic: true,
            strokeColor: "#f6c26b",
            strokeOpacity: 0.95,
            strokeWeight: 4
          });
          map.fitBounds(bounds, 48);
        }

        setMapState("ready-2d");
        setMapNote("Google Maps 3D is unavailable in this browser or key setup, so the app is showing a live 2D map instead.");
      } catch (error) {
        if (!cancelled) {
          console.error("Google Maps 3D failed to render.", error);
          setMapState("fallback");
          setMapNote(error instanceof Error ? error.message : "Google Maps failed to load.");
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
          {mapState === "ready-3d"
            ? "Google Maps 3D"
            : mapState === "ready-2d"
              ? "Google Maps live 2D"
            : GOOGLE_MAPS_API_KEY
              ? mapState === "loading"
                ? "Loading live map"
                : "Fallback projection"
              : "Set VITE_GOOGLE_MAPS_API_KEY for 3D"}
        </span>
      </div>

      <div className="map-frame">
        {shouldRenderGoogleHost ? (
          <div ref={containerRef} className="google-map-host" />
        ) : (
          <FallbackGlobe stops={stops} selectedStopId={selectedStopId} />
        )}
      </div>
      {mapNote ? (
        <p className="map-note">
          {mapNote} Check the browser console, confirm Maps JavaScript API is enabled, and verify your key allows this localhost origin.
        </p>
      ) : null}
    </section>
  );
}
