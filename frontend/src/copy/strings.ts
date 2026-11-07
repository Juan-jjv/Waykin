// ALL user-facing text lives here, so the banned-word lint has one place to watch.
import type { AbstainReason, RouteLabel } from "../api/types";

export const routeLabelText: Record<RouteLabel, string> = {
  fastest: "Fastest",
  balanced: "Balanced",
  lower_exposure: "Lower-exposure",
};

export const abstainCopy: Record<AbstainReason, { headline: string; body: string }> = {
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

export const strings = {
  appName: "WayKin",
  tagline: "Walking routes by reported incidents",
  cantReach: "Can't reach the WayKin server",
  retry: "Retry",
  opening: "Opening the map…",
  tapHint: "Tap the map once for the start and again for the end.",
  findHint: "Choose Find routes to compare fastest, balanced, and lower-exposure.",
  findRoutes: "Find routes",
  finding: "Finding routes",
  start: "Start",
  end: "End",
  tapTheMap: "Tap the map",
  swap: "Swap",
  clear: "Clear",
  presets: "Demo walks",
  catchment: "Catchment radius",
  incidents: "Reported incidents",
  incidentsOn: "Show reported incidents",
  categories: "Categories",
  outsideArea: "Pick points inside the highlighted area",
  noPath: "No walking route found between these points",
  streetsUnavailable: "Couldn't follow the streets between these points. Try again.",
  showSegments: "Show segments",
  startWalk: "Start walk with this route",
  walkSaved: "Route saved on this device. The walker screen is the next slice.",
  walkSaveFailed: "Couldn't save the route on this device.",
  radiusChanges: "The answer changes with the catchment radius",
  whyAbstain: "Why WayKin abstains",
  abstainDisclosure:
    "We only recommend a different route when it has at least 15% fewer reports in 90% of 500 simulations and adds at most 25% to your time.",
  noRecommendation: "No single recommendation",
  hideDetails: "Hide details",
  showDetails: "Details",
  mapCredit: "OpenFreeMap © OpenMapTiles © OpenStreetMap",
  switchToDark: "Switch to dark map",
  switchToLight: "Switch to light map",
  selectRoute: (label: string) => `Select ${label}`,
  recommended: (label: string) => `Recommended: ${label}`,
  holdsIn: (draws: number, n: number) => `Holds in ${draws} of ${n} simulations`,
  incidentCount: (n: number) => `${n} reported ${n === 1 ? "incident" : "incidents"}, last 90 days`,
  incidentCategory: (category: string, n: number) => `${category.replace(/_/g, " ")}: ${n}`,
  asOf: (date: string) => `as of ${date}`,
  walkPlaceholder: "Walker screen arrives in Phase 3.",
  familyPlaceholder: "Family screen arrives in Phase 3.",
  journey: (id: string | undefined) => `Journey ${id}`,
  backToPlan: "Back to plan",
  messages: {
    recommendLower:
      "Lower-exposure has fewer reported incidents in most simulations, and the extra walk stays within the time limit.",
    recommendBalanced:
      "Balanced has fewer reported incidents than the fastest route in most simulations at this radius.",
    explainFastest: "Shortest walk. The other routes are compared with this one.",
    explainBalanced: "A few more minutes, with fewer reported incidents than the fastest route.",
    explainLower: "Fewest reported incidents of the three, with a longer walk.",
    explainFastestOverlap: "Shortest walk. The reported-incident range overlaps the other routes.",
    explainBalancedOverlap: "Close to the fastest walk. The reported-incident range overlaps it.",
    explainLowerOverlap: "A slightly longer walk. The reported-incident range still overlaps the others.",
  },
};
