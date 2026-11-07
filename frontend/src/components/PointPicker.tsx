import { CircleMarker, Tooltip, useMapEvents } from "react-leaflet";
import type { LatLon } from "../api/types";

/** First click sets the origin, second the destination; further clicks move the destination. */
export function PointPicker({ origin, destination, onChange }: {
  origin: LatLon | null;
  destination: LatLon | null;
  onChange: (origin: LatLon | null, destination: LatLon | null) => void;
}) {
  useMapEvents({
    click(e) {
      const p = { lat: e.latlng.lat, lon: e.latlng.lng };
      if (!origin) onChange(p, destination);
      else onChange(origin, p);
    },
  });
  return (
    <>
      {origin && (
        <CircleMarker center={[origin.lat, origin.lon]} radius={8} pathOptions={{ color: "#0f172a", fillColor: "#fff", fillOpacity: 1, weight: 3 }}>
          <Tooltip permanent direction="top">Start</Tooltip>
        </CircleMarker>
      )}
      {destination && (
        <CircleMarker center={[destination.lat, destination.lon]} radius={8} pathOptions={{ color: "#0f172a", fillColor: "#0f172a", fillOpacity: 1 }}>
          <Tooltip permanent direction="top">Destination</Tooltip>
        </CircleMarker>
      )}
    </>
  );
}
