import { Polyline, Tooltip } from "react-leaflet";
import type { RouteOption } from "../api/types";
import { LABELS } from "../copy/strings";

// Never red or green for routes: they imply a judgment.
export const ROUTE_COLORS: Record<string, string> = {
  fastest: "#64748b",
  balanced: "#2563eb",
  lower_exposure: "#7c3aed",
};
const TOP_SEGMENT = "#d97706";

export function RouteLayer({ routes, selectedId, onSelect }: {
  routes: RouteOption[];
  selectedId: string | null;
  onSelect: (id: string) => void;
}) {
  // The selected route is drawn last, so it sits on top.
  const ordered = [...routes.filter((r) => r.route_id !== selectedId), ...routes.filter((r) => r.route_id === selectedId)];
  return (
    <>
      {ordered.map((r) => {
        const selected = r.route_id === selectedId;
        return (
          <Polyline
            key={r.route_id}
            positions={r.geometry.map(([lat, lon]) => [lat, lon] as [number, number])}
            pathOptions={{ color: ROUTE_COLORS[r.label], weight: selected ? 7 : 4, opacity: selected ? 0.95 : 0.55 }}
            eventHandlers={{ click: () => onSelect(r.route_id) }}
          >
            <Tooltip sticky>{LABELS[r.label]}</Tooltip>
          </Polyline>
        );
      })}
      {routes
        .filter((r) => r.route_id === selectedId)
        .flatMap((r) => r.top_segments)
        .map((s) => (
          <Polyline
            key={`top-${s.edge_id}`}
            positions={s.geometry.map(([lat, lon]) => [lat, lon] as [number, number])}
            pathOptions={{ color: TOP_SEGMENT, weight: 11, opacity: 0.45 }}
          />
        ))}
    </>
  );
}
