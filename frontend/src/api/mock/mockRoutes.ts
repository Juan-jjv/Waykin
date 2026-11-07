import metaJson from "./fixtures/meta.json";
import { traceWalkingRoutes, type TracedRoute } from "./streetRoute";
import type {
  Decision,
  Interval,
  LatLon,
  Meta,
  Provenance,
  RouteLabel,
  RouteOption,
  RoutesRequest,
  RoutesResponse,
  TopSegment,
} from "../types";
import { abstainCopy, strings } from "../../copy/strings";

const meta = metaJson as Meta;
const ABSTAIN_PRESET_ID = "overlap";

const RADIUS_DECISIONS: Record<string, string> = {
  "50": "recommend:balanced",
  "100": "recommend:lower_exposure",
  "200": "abstain:indistinguishable",
};

const SEPARATED: Record<RouteLabel, Interval> = {
  fastest: { p10: 8.4, p50: 12.6, p90: 17.2, mean: 12.8 },
  balanced: { p10: 5.1, p50: 8.4, p90: 11.9, mean: 8.6 },
  lower_exposure: { p10: 2.8, p50: 5.2, p90: 8.1, mean: 5.4 },
};

const OVERLAP: Record<RouteLabel, Interval> = {
  fastest: { p10: 7.4, p50: 10.4, p90: 14.2, mean: 10.6 },
  balanced: { p10: 7.1, p50: 10.1, p90: 14.6, mean: 10.4 },
  lower_exposure: { p10: 6.8, p50: 9.8, p90: 14.8, mean: 10.2 },
};

export async function buildMockRoutes(request: RoutesRequest): Promise<RoutesResponse> {
  const radius = request.radius_m ?? meta.default_radius_m;
  const { origin, destination } = request;

  if (!insideBBox(origin, meta.bbox) || !insideBBox(destination, meta.bbox)) {
    throw Object.assign(new Error("outside_area"), { code: "outside_area" as const });
  }
  if (haversine(origin, destination) < 25) {
    throw Object.assign(new Error("no_path"), { code: "no_path" as const });
  }

  const traced = await traceWalkingRoutes(origin, destination);
  if (!traced || traced.length === 0) {
    throw Object.assign(new Error("no_path"), { code: "no_path" as const });
  }

  const overlap = matchesPreset(origin, destination, ABSTAIN_PRESET_ID);
  const counts = overlap || radius === 200 ? "overlap" : "separated";
  const routes = makeRoutes(traced, origin, destination, radius, counts);
  const decision = makeDecision(routes, radius, overlap);

  return {
    provenance: provenanceFor(radius),
    origin_snapped: snapped(traced[0].geometry[0], origin),
    destination_snapped: snapped(traced[0].geometry[traced[0].geometry.length - 1], destination),
    routes,
    decision,
    blocked_edge_count: 0,
  };
}

function snapped(point: [number, number] | undefined, fallback: LatLon): LatLon {
  if (!point) return fallback;
  return { lat: point[0], lon: point[1] };
}

function makeDecision(routes: RouteOption[], radius: number, overlapPreset: boolean): Decision {
  const fastest = routes.find((route) => route.label === "fastest");
  const balanced = routes.find((route) => route.label === "balanced");
  const lower = routes.find((route) => route.label === "lower_exposure");
  const base = {
    thresholds: meta.thresholds,
    n_draws: meta.n_draws,
    radius_decisions: overlapPreset ? null : RADIUS_DECISIONS,
    radius_sensitive: overlapPreset ? false : true,
  };

  if (overlapPreset || radius === 200) {
    return {
      ...base,
      status: "abstain",
      recommended_route_id: null,
      reason: "indistinguishable",
      message: abstainCopy.indistinguishable.body,
    };
  }

  if (!fastest || (!balanced && !lower)) {
    return {
      ...base,
      status: "abstain",
      recommended_route_id: null,
      reason: "no_alternative",
      message: abstainCopy.no_alternative.body,
      radius_sensitive: false,
      radius_decisions: null,
    };
  }

  const cap = fastest.minutes * (1 + meta.thresholds.max_extra_time);
  if (radius === 50 && balanced && balanced.minutes <= cap) {
    return {
      ...base,
      status: "recommend",
      recommended_route_id: balanced.route_id,
      reason: null,
      message: strings.messages.recommendBalanced,
    };
  }
  if (lower && lower.minutes <= cap) {
    return {
      ...base,
      status: "recommend",
      recommended_route_id: lower.route_id,
      reason: null,
      message: strings.messages.recommendLower,
    };
  }
  if (balanced && balanced.minutes <= cap) {
    return {
      ...base,
      status: "recommend",
      recommended_route_id: balanced.route_id,
      reason: null,
      message: strings.messages.recommendBalanced,
    };
  }
  return {
    ...base,
    status: "abstain",
    recommended_route_id: null,
    reason: "too_costly",
    message: abstainCopy.too_costly.body,
    radius_sensitive: true,
  };
}

function makeRoutes(
  traced: TracedRoute[],
  origin: LatLon,
  destination: LatLon,
  radius: number,
  counts: "separated" | "overlap",
): RouteOption[] {
  const labels = labelsFor(traced);
  const fastestMinutes = traced[0].distance / 80;
  const table = counts === "overlap" ? OVERLAP : SEPARATED;
  const factor = radius === 50 ? 0.62 : radius === 200 ? 1.35 : 1;
  const fastestLabel = labels[0] ?? "fastest";
  const fastestExposure = scaleInterval(table[fastestLabel], factor);

  return traced.map((route, index) => {
    const label = labels[index] ?? "fastest";
    const minutes = route.distance / 80;
    const exposure = scaleInterval(table[label], factor);
    const seed = 100 + index * 100;
    return {
      route_id: routeId(label, origin, destination, radius),
      label,
      minutes: round1(minutes),
      extra_minutes: round1(Math.max(0, minutes - fastestMinutes)),
      distance_m: Math.round(route.distance),
      exposure,
      exposure_diff_vs_fastest: label === "fastest" ? null : diffInterval(exposure, fastestExposure),
      draws_better: drawsFor(label, counts, radius),
      geometry: route.geometry,
      edge_ids: route.steps.length > 0 ? route.steps.map((_, stepIndex) => seed + stepIndex + 1) : [seed],
      top_segments: topSegments(route, seed, exposure.p50),
      explanation: explanation(label, counts),
    };
  });
}

function labelsFor(traced: TracedRoute[]): RouteLabel[] {
  if (traced.length === 1) return ["fastest"];
  if (traced.length === 2) {
    const extra = traced[1].distance / traced[0].distance - 1;
    return ["fastest", extra >= 0.12 ? "lower_exposure" : "balanced"];
  }
  return ["fastest", "balanced", "lower_exposure"];
}

function drawsFor(label: RouteLabel, counts: "separated" | "overlap", radius: number): number | null {
  if (label === "fastest") return null;
  if (counts === "overlap") return label === "balanced" ? 214 : 188;
  if (label === "balanced") return radius === 50 ? 468 : 452;
  return radius === 50 ? 401 : 471;
}

function explanation(label: RouteLabel, mode: "separated" | "overlap"): string {
  if (mode === "overlap") {
    if (label === "fastest") return strings.messages.explainFastestOverlap;
    if (label === "balanced") return strings.messages.explainBalancedOverlap;
    return strings.messages.explainLowerOverlap;
  }
  if (label === "fastest") return strings.messages.explainFastest;
  if (label === "balanced") return strings.messages.explainBalanced;
  return strings.messages.explainLower;
}

function topSegments(route: TracedRoute, seed: number, attributedBase: number): TopSegment[] {
  const named = route.steps.filter((step) => step.name && step.geometry.length >= 2);
  named.sort((a, b) => b.distance - a.distance);
  const picked = named.slice(0, 3);
  if (picked.length === 0) {
    const start = Math.floor(route.geometry.length * 0.35);
    const end = Math.max(start + 2, Math.ceil(route.geometry.length * 0.65));
    return [
      {
        edge_id: seed + 1,
        name: null,
        attributed: round1(attributedBase * 0.4),
        geometry: route.geometry.slice(start, end),
      },
    ];
  }
  const total = picked.reduce((sum, step) => sum + step.distance, 0) || 1;
  return picked.map((step, index) => ({
    edge_id: seed + index + 1,
    name: step.name,
    attributed: round1(attributedBase * (step.distance / total) * 0.55),
    geometry: step.geometry,
  }));
}

function provenanceFor(radius: number): Provenance {
  return { ...meta.provenance, radius_m: radius };
}

function matchesPreset(origin: LatLon, destination: LatLon, id: string): boolean {
  const preset = meta.demo_presets.find((item) => item.id === id);
  if (!preset) return false;
  return haversine(origin, preset.origin) < 40 && haversine(destination, preset.destination) < 40;
}

function insideBBox(point: LatLon, bbox: number[]): boolean {
  const [west, south, east, north] = bbox;
  return point.lon >= west && point.lon <= east && point.lat >= south && point.lat <= north;
}

function haversine(a: LatLon, b: LatLon): number {
  const radius = 6_371_000;
  const p1 = (a.lat * Math.PI) / 180;
  const p2 = (b.lat * Math.PI) / 180;
  const dp = ((b.lat - a.lat) * Math.PI) / 180;
  const dl = ((b.lon - a.lon) * Math.PI) / 180;
  const h = Math.sin(dp / 2) ** 2 + Math.cos(p1) * Math.cos(p2) * Math.sin(dl / 2) ** 2;
  return 2 * radius * Math.asin(Math.min(1, Math.sqrt(h)));
}

function diffInterval(route: Interval, fastest: Interval): Interval {
  return {
    p10: round1(route.p10 - fastest.p10),
    p50: round1(route.p50 - fastest.p50),
    p90: round1(route.p90 - fastest.p90),
    mean: round1(route.mean - fastest.mean),
  };
}

function scaleInterval(interval: Interval, factor: number): Interval {
  return {
    p10: round1(interval.p10 * factor),
    p50: round1(interval.p50 * factor),
    p90: round1(interval.p90 * factor),
    mean: round1(interval.mean * factor),
  };
}

function routeId(label: string, origin: LatLon, destination: LatLon, radius: number): string {
  const text = `${label}:${origin.lat.toFixed(5)}:${origin.lon.toFixed(5)}:${destination.lat.toFixed(5)}:${destination.lon.toFixed(5)}:${radius}`;
  let hash = 2_166_136_261;
  for (let index = 0; index < text.length; index += 1) {
    hash ^= text.charCodeAt(index);
    hash = Math.imul(hash, 16_777_619);
  }
  return (hash >>> 0).toString(16).padStart(8, "0").slice(0, 10);
}

function round1(value: number): number {
  return Math.round(value * 10) / 10;
}
