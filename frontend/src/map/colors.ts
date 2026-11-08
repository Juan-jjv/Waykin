import type { RouteLabel } from "../api/types";

export const ROUTE_COLORS: Record<RouteLabel, string> = {
  fastest: "#64748b",
  lower_exposure: "#7c3aed",
};

export const SEGMENT_COLOR = "#d97706";

export const INCIDENT_COLORS = {
  light: { stroke: "#ffffff" },
  dark: { stroke: "#fecaca" },
};

/** Severity runs 1 (least serious) to 5 (most), the same weights walking routes use (meta.severity). */
export const SEVERITY_MIN = 1;
export const SEVERITY_MAX = 5;

/** Light red to dark red, one stop per severity level 1..5. The dark map starts lighter so the top stays visible. */
export const SEVERITY_RAMP: Record<"light" | "dark", string[]> = {
  light: ["#fca5a5", "#f87171", "#dc2626", "#991b1b", "#450a0a"],
  dark: ["#fecaca", "#fca5a5", "#ef4444", "#b91c1c", "#7f1d1d"],
};

/** A location's shade: the weight of its most serious category with reports (1 when nothing is known). */
export function severityOf(byCategory: Record<string, number>, severity: Record<string, number>): number {
  let worst = SEVERITY_MIN;
  for (const [category, count] of Object.entries(byCategory)) {
    if (count > 0) worst = Math.max(worst, severity[category] ?? SEVERITY_MIN);
  }
  return Math.min(worst, SEVERITY_MAX);
}

/** The most serious category with reports, or null. */
export function worstCategory(byCategory: Record<string, number>, severity: Record<string, number>): string | null {
  let best: string | null = null;
  for (const [category, count] of Object.entries(byCategory)) {
    if (count > 0 && (best === null || (severity[category] ?? 0) > (severity[best] ?? 0))) best = category;
  }
  return best;
}

/** MapLibre expression: colour by the feature's `sev` property along the ramp. */
export function severityColorExpression(appearance: "light" | "dark") {
  const stops = SEVERITY_RAMP[appearance].flatMap((color, index) => [SEVERITY_MIN + index, color]);
  return ["interpolate", ["linear"], ["get", "sev"], ...stops];
}
