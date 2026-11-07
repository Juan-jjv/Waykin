import { CircleMarker, Tooltip } from "react-leaflet";
import { useIncidents } from "../api/hooks";
import { STR } from "../copy/strings";

/** Grows with the count but stays capped, so a busy intersection doesn't cover its neighbours. */
export function incidentRadius(count: number): number {
  return Math.min(4 + Math.sqrt(count) * 1.5, 16);
}

/** Published points only, as served by /api/incidents. One neutral colour: the map shows counts, not a rating of places. */
export function IncidentLayer({ radiusM }: { radiusM: number }) {
  const incidents = useIncidents(radiusM, [], true);
  return (
    <>
      {incidents.data?.points.map((p) => (
        <CircleMarker
          key={p.location_id}
          center={[p.lat, p.lon]}
          radius={incidentRadius(p.count)}
          pathOptions={{ color: "#475569", weight: 1, fillColor: "#64748b", fillOpacity: 0.45 }}
        >
          <Tooltip>
            <strong>{STR.incidentCount(p.count)}</strong>
            {Object.entries(p.by_category).map(([category, n]) => (
              <div key={category}>{STR.incidentCategory(category, n)}</div>
            ))}
          </Tooltip>
        </CircleMarker>
      ))}
    </>
  );
}
