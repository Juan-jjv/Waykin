// ALL user-facing text lives here, so the banned-word lint has one place to watch.
import type { AbstainReason } from "../api/types";

export const STR = {
  appName: "WayKin",
  tagline: "Walking routes, honest about the data",
  serverDown: "Can't reach the WayKin server",
  retry: "Retry",
  pickOrigin: "Tap the map to set your start",
  pickDestination: "Tap the map to set your destination",
  findRoutes: "Find routes",
  finding: "Comparing routes…",
  clear: "Clear",
  swap: "Swap",
  outsideArea: "Pick points inside the highlighted area",
  noPath: "No walking route found between these points",
  asOf: (d: string) => `as of ${d}`,
  incidentCount: (n: number) => `${n} reported ${n === 1 ? "incident" : "incidents"}, last 90 days`,
  incidentCategory: (category: string, n: number) => `${category.replace(/_/g, " ")}: ${n}`,
  showDisclaimer: "About this data",
  hideDisclaimer: "Hide",
  recommended: (label: string) => `Recommended: ${label}`,
  holds: (n: number, total: number) => `Holds in ${n} of ${total} simulations`,
  exposure: (p50: number, p10: number, p90: number) =>
    `≈ ${p50.toFixed(1)} reported incidents (${p10.toFixed(1)}–${p90.toFixed(1)})`,
  fewer: (d50: number, d10: number, d90: number) =>
    d50 < 0
      ? `about ${Math.abs(d50).toFixed(1)} fewer (${Math.abs(d90).toFixed(1)} to ${Math.abs(d10).toFixed(1)} fewer)`
      : "about the same or more",
  extra: (m: number) => `+${Math.round(m)} min`,
  minutes: (m: number) => `${Math.round(m)} min`,
  whyAbstain:
    "We only recommend a different route when it has at least 15% fewer reports in 90% of 500 simulations and adds at most 25% to your time.",
  whyAbstainTitle: "Why WayKin abstains",
  walkPlaceholder: "Walker screen arrives in Phase 3.",
  familyPlaceholder: "Family screen arrives in Phase 3.",
};

export const LABELS: Record<string, string> = {
  fastest: "Fastest",
  balanced: "Balanced",
  lower_exposure: "Lower-exposure",
};

export const ABSTAIN: Record<AbstainReason, { headline: string; body: string }> = {
  thin_data: {
    headline: "Not enough reports to compare",
    body: "There are too few reported incidents near these routes to tell them apart. Take the route that suits you.",
  },
  indistinguishable: {
    headline: "These routes are about the same",
    body: "The reported-incident counts overlap too much to call one lower. It doesn't really matter which you take.",
  },
  too_costly: {
    headline: "A lower-count route would take much longer",
    body: "The only routes with clearly fewer reports add more than 25% to your walk time.",
  },
  no_alternative: {
    headline: "There's one sensible route",
    body: "No other reasonable route exists for this trip.",
  },
};
