import { useEffect, useMemo, useRef } from "react";
import { Map as MapLibreMap, Marker, type MapMouseEvent } from "maplibre-gl";
import type { LatLon } from "../api/tmp-types";
import { formatCoord } from "../copy/format";
import { strings } from "../copy/strings";
import { useWaykinMap } from "../map/context";

interface PointMarkerProps {
  origin: LatLon | null;
  destination: LatLon | null;
  onOrigin: (point: LatLon) => void;
  onDestination: (point: LatLon) => void;
}

export function PointMarkers({ origin, destination, onOrigin, onDestination }: PointMarkerProps) {
  const map = useWaykinMap();
  const onOriginRef = useRef(onOrigin);
  const onDestinationRef = useRef(onDestination);
  onOriginRef.current = onOrigin;
  onDestinationRef.current = onDestination;
  const originRef = useRef(origin);
  const destinationRef = useRef(destination);
  originRef.current = origin;
  destinationRef.current = destination;

  useEffect(() => {
    const onClick = (event: MapMouseEvent) => {
      const target = event.originalEvent.target;
      if (target instanceof Element && target.closest(".maplibregl-marker, .maplibregl-ctrl, .wk-pin-wrap, .wk-end-wrap")) {
        return;
      }
      const layers = ["waykin-incidents", "waykin-route-hit"].filter((id) => Boolean(map.getLayer(id)));
      if (layers.length > 0 && map.queryRenderedFeatures(event.point, { layers }).length > 0) return;
      const point = { lat: event.lngLat.lat, lon: event.lngLat.lng };
      if (!originRef.current) onOriginRef.current(point);
      else if (!destinationRef.current) onDestinationRef.current(point);
    };
    map.on("click", onClick);
    return () => {
      map.off("click", onClick);
    };
  }, [map]);

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

export function PointSummary({
  origin,
  destination,
  onSwap,
  onClear,
}: {
  origin: LatLon | null;
  destination: LatLon | null;
  onSwap: () => void;
  onClear: () => void;
}) {
  const rows = useMemo(
    () => [
      { label: strings.start, point: origin },
      { label: strings.end, point: destination },
    ],
    [origin, destination],
  );

  return (
    <div className="point-block">
      <div className="points">
        {rows.map((row) => (
          <div className="point-row" key={row.label}>
            <span>{row.label}</span>
            <span>{row.point ? formatCoord(row.point.lat, row.point.lon) : strings.tapTheMap}</span>
          </div>
        ))}
      </div>
      <div className="point-actions">
        <button type="button" className="btn-quiet" onClick={onSwap} disabled={!origin || !destination}>
          {strings.swap}
        </button>
        <button type="button" className="btn-quiet" onClick={onClear} disabled={!origin && !destination}>
          {strings.clear}
        </button>
      </div>
    </div>
  );
}
