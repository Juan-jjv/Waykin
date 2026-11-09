import { useEffect, useRef } from "react";
import { Map as MapLibreMap, Marker } from "maplibre-gl";
import type { Place } from "../api/geocode";
import type { LatLon } from "../api/types";
import { strings } from "../copy/strings";
import { useWaykinMap } from "../map/context";
import { SwapIcon } from "./icons";
import { PlaceSearch, type QuickPlace } from "./PlaceSearch";

interface PointMarkerProps {
  origin: LatLon | null;
  destination: LatLon | null;
  onOrigin: (point: LatLon) => void;
  onDestination: (point: LatLon) => void;
}

/** Start and end pins. Points are chosen by search; dragging a pin fine-tunes it. */
export function PointMarkers({ origin, destination, onOrigin, onDestination }: PointMarkerProps) {
  const map = useWaykinMap();
  const onOriginRef = useRef(onOrigin);
  const onDestinationRef = useRef(onDestination);
  onOriginRef.current = onOrigin;
  onDestinationRef.current = onDestination;

  useDragMarker(map, origin, "start", (point) => onOriginRef.current(point));
  useDragMarker(map, destination, "end", (point) => onDestinationRef.current(point));

  return null;
}

function useDragMarker(
  map: MapLibreMap,
  point: LatLon | null,
  kind: "start" | "end",
  onMove: (point: LatLon) => void,
) {
  const markerRef = useRef<Marker | null>(null);
  const onMoveRef = useRef(onMove);
  onMoveRef.current = onMove;

  useEffect(() => {
    if (!point) {
      markerRef.current?.remove();
      markerRef.current = null;
      return;
    }
    if (!markerRef.current) {
      const marker = new Marker({
        element: kind === "start" ? startElement() : endElement(),
        anchor: kind === "start" ? "center" : "bottom",
        draggable: true,
      })
        .setLngLat([point.lon, point.lat])
        .addTo(map);
      marker.on("dragend", () => {
        const lngLat = marker.getLngLat();
        onMoveRef.current({ lat: lngLat.lat, lon: lngLat.lng });
      });
      markerRef.current = marker;
      return;
    }
    const current = markerRef.current.getLngLat();
    if (Math.abs(current.lat - point.lat) > 1e-7 || Math.abs(current.lng - point.lon) > 1e-7) {
      markerRef.current.setLngLat([point.lon, point.lat]);
    }
  }, [map, point, kind]);

  useEffect(() => {
    return () => {
      markerRef.current?.remove();
      markerRef.current = null;
    };
  }, [map]);
}

function startElement(): HTMLElement {
  const wrap = document.createElement("div");
  wrap.className = "wk-pin-wrap";
  wrap.innerHTML = `<div class="wk-start"></div><span class="wk-pin-label">${strings.start}</span>`;
  return wrap;
}

function endElement(): HTMLElement {
  const wrap = document.createElement("div");
  wrap.className = "wk-end-wrap";
  wrap.innerHTML = `<svg class="wk-end" viewBox="0 0 28 36" aria-hidden="true">
    <path d="M14 1.5C7.4 1.5 2.2 6.6 2.2 13.1 2.2 21.6 14 34.2 14 34.2s11.8-12.6 11.8-21.1C25.8 6.6 20.6 1.5 14 1.5z" fill="var(--pin)" stroke="white" stroke-width="2"/>
    <circle cx="14" cy="13" r="4.2" fill="var(--pin-contrast)"/>
  </svg><span class="wk-pin-label">${strings.end}</span>`;
  return wrap;
}

export function PointSearch({
  originLabel,
  destinationLabel,
  bbox,
  canSwap,
  canClear,
  onOrigin,
  onDestination,
  onSwap,
  onClear,
  startChoices = [],
  endChoices = [],
}: {
  originLabel: string | null;
  destinationLabel: string | null;
  bbox: number[];
  canSwap: boolean;
  canClear: boolean;
  onOrigin: (place: Place) => void;
  onDestination: (place: Place) => void;
  onSwap: () => void;
  onClear: () => void;
  startChoices?: QuickPlace[];
  endChoices?: QuickPlace[];
}) {
  return (
    <section className="point-block" aria-labelledby="plan-title">
      <div className="section-head">
        <h2 id="plan-title" className="section-title">{strings.planTitle}</h2>
        <button type="button" className="text-btn" onClick={onClear} disabled={!canClear}>
          {strings.clear}
        </button>
      </div>
      <div className="points">
        <PlaceSearch
          label={strings.start}
          placeholder={strings.searchStart}
          value={originLabel}
          bbox={bbox}
          onSelect={onOrigin}
          quick={startChoices}
          marker="start"
        />
        <PlaceSearch
          label={strings.end}
          placeholder={strings.searchEnd}
          value={destinationLabel}
          bbox={bbox}
          onSelect={onDestination}
          quick={endChoices}
          marker="end"
        />
        <button
          type="button"
          className="swap-btn"
          onClick={onSwap}
          disabled={!canSwap}
          aria-label={strings.swapLabel}
          title={strings.swapLabel}
        >
          <SwapIcon />
        </button>
      </div>
    </section>
  );
}
