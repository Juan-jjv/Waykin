import type { RouteLabel } from "../api/types";

export const ROUTE_COLORS: Record<RouteLabel, string> = {
  fastest: "#64748b",
  balanced: "#2563eb",
  lower_exposure: "#7c3aed",
};

export const SEGMENT_COLOR = "#d97706";

export const INCIDENT_COLORS = {
  light: { fill: "#dc2626", stroke: "#991b1b" },
  dark: { fill: "#ef4444", stroke: "#fecaca" },
};
