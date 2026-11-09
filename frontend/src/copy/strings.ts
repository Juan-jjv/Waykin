// ALL user-facing text lives here, so the banned-word lint has one place to watch.
import type { AbstainReason, RouteLabel, TravelMode } from "../api/types";

export const routeLabelText: Record<RouteLabel, string> = {
  fastest: "Fastest",
  lower_exposure: "Lower-exposure",
};

export const modeText: Record<TravelMode, string> = {
  walk: "Walk",
  drive: "Drive",
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
    body: "The only routes with clearly fewer reports add more than {cap} to your travel time.",
  },
  no_alternative: {
    headline: "There's one sensible route",
    body: "No other reasonable route exists for this trip.",
  },
};

/** Whole-number percent for a share such as thresholds.max_extra_time (0.8 -> "80%"). */
export const percent = (share: number) => `${Math.round(share * 100)}%`;

/** Abstain body with the server's time cap filled in. */
export const abstainBody = (reason: AbstainReason, maxExtra: number) =>
  abstainCopy[reason].body.replace("{cap}", percent(maxExtra));

export const strings = {
  appName: "WayKin",
  travelMode: "Travel mode",
  cantReach: "Can't reach the WayKin server",
  retry: "Retry",
  opening: "Opening the map…",
  findRoutes: "Find routes",
  finding: "Finding routes",
  start: "Start",
  end: "End",
  searchStart: "Search for a start",
  searchEnd: "Search for a destination",
  searching: "Searching…",
  noMatches: "No matches in Edmonton",
  searchFailed: "Search is unavailable right now. Try again.",
  yourLocation: "Your location",
  locating: "Finding your location…",
  locationUnavailable: "This browser can't share its location.",
  locationDenied: "Location is off for this site. Allow it in the browser, or search instead.",
  locationTimeout: "Couldn't get your location just now. Try again, or search instead.",
  locationOutside: "You're outside the map area. Search for a start instead.",
  droppedPin: "Dropped pin",
  personNear: (street: string) => `Near ${street}`,
  startHere: "Start here",
  endHere: "End here",
  stationsTitle: "Police stations",
  stationsAll: (count: number) => `Show all ${count}`,
  stationsFewer: "Show fewer",
  stationRoute: "Route here",
  stationNeedsStart: "Choose a start above, then tap the station again.",
  presetStart: (name: string) => `${name} (start)`,
  presetEnd: (name: string) => `${name} (end)`,
  swapLabel: "Swap start and end",
  clear: "Clear",
  planTitle: "Plan a route",
  presets: "Demo walks",
  expandPanel: "Expand panel",
  collapsePanel: "Collapse panel",
  recommendedBadge: "Recommended",
  exposureNoun: "reported incidents",
  vsFastest: "vs fastest",
  likelyRange: (low: string, high: string) => `Likely ${low}–${high}`,
  routeSummary: (label: string, minutes: string) => `${label}, ${minutes}`,
  incidents: "Reported incidents",
  incidentsOn: "Show reported incidents",
  severityHigh: "H",
  severityLow: "L",
  severityLegendLabel: "Dot colour: dark red at the top for the most serious reports, fading to light red for the least serious",
  mostSerious: (category: string) => `Most serious: ${category.replace(/_/g, " ")}`,
  categories: "Categories",
  filters: "Map filters",
  reportedIn: "Reported in",
  dateWindows: [
    { days: 1, label: "Last 24 hours" },
    { days: 2, label: "Last 48 hours" },
    { days: 7, label: "Last week" },
    { days: 30, label: "Last month" },
  ],
  dateNote: (date: string) => `Data as of ${date}`,
  outsideArea: "Pick points inside the highlighted area",
  noPath: (mode: TravelMode) => `No ${mode === "drive" ? "driving" : "walking"} route found between these points`,
  streetsUnavailable: "Couldn't follow the streets between these points. Try again.",
  showSegments: "Show segments",
  startWalk: "Start walk with this route",
  startDrive: "Start drive with this route",
  walkExposureNoun: "incident score",
  walkSaveFailed: "Couldn't save the route on this device.",
  whyAbstain: "Why WayKin abstains",
  abstainDisclosure: (maxExtra: number) =>
    `We only recommend a different route when it has at least 15% fewer reports in 90% of 500 simulations and adds at most ${percent(maxExtra)} to your time.`,
  noRecommendation: "No single recommendation",
  hideDetails: "Hide details",
  showDetails: "Details",
  mapCredit: "OpenFreeMap © OpenMapTiles © OpenStreetMap",
  switchToDark: "Switch to dark map",
  switchToLight: "Switch to light map",
  recommended: (label: string) => `Recommended: ${label}`,
  holdsIn: (draws: number, n: number) => `Holds in ${draws} of ${n} simulations`,
  incidentCount: (n: number, window = "last 30 days") =>
    `${n} reported ${n === 1 ? "incident" : "incidents"}, ${window.toLowerCase()}`,
  incidentCategory: (category: string, n: number) => `${category.replace(/_/g, " ")}: ${n}`,
  asOf: (date: string) => `as of ${date}`,
  journey: (id: string | undefined) => `Journey ${id}`,
  backToPlan: "Back to plan",
  messages: {
    recommendLower:
      "Lower-exposure has fewer reported incidents in most simulations, and the extra walk stays within the time limit.",
    explainFastest: "Shortest walk. The other routes are compared with this one.",
    explainLower: "Fewest reported incidents of the three, with a longer walk.",
    explainFastestOverlap: "Shortest walk. The reported-incident range overlaps the other routes.",
    explainLowerOverlap: "A slightly longer walk. The reported-incident range still overlaps the others.",
  },
};
