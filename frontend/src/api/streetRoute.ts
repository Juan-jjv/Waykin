import type { LatLon } from "./tmp-types";

const ROUTER = "https://router.project-osrm.org/route/v1/foot";
const OFFSETS_M = [150, -190, 280, -340, 460, -520];

export class TraceError extends Error {
  constructor() {
    super("trace");
    this.name = "TraceError";
  }
}

export interface TracedStep {
  name: string;
  distance: number;
  geometry: [number, number][];
}

export interface TracedRoute {
  distance: number;
  geometry: [number, number][];
  steps: TracedStep[];
}

interface OsrmStep {
  name?: string;
  distance: number;
  geometry?: { coordinates?: [number, number][] };
}

interface OsrmRoute {
  distance: number;
  geometry?: { coordinates?: [number, number][] };
  legs?: { steps?: OsrmStep[] }[];
}

interface OsrmResponse {
  code?: string;
  routes?: OsrmRoute[];
}

export async function traceWalkingRoutes(origin: LatLon, destination: LatLon): Promise<TracedRoute[] | null> {
  const direct = await requestRoute([origin, destination]);
  if (!direct) return null;

  const viaRoutes = await Promise.all(
    OFFSETS_M.map(async (meters) => {
      try {
        return await requestRoute([origin, offsetPoint(origin, destination, meters), destination]);
      } catch (error) {
        if (error instanceof TraceError) return null;
        throw error;
      }
    }),
  );

  const chosen: TracedRoute[] = [direct];
  const ranked = viaRoutes
    .filter((route): route is TracedRoute => route !== null)
    .filter((route) => route.distance > direct.distance + 40 && route.distance < direct.distance * 1.4)
    .sort((a, b) => a.distance - b.distance);

  for (const candidate of ranked) {
    if (chosen.length >= 3) break;
    if (chosen.every((existing) => corridorsDiffer(existing.geometry, candidate.geometry))) {
      chosen.push(candidate);
    }
  }

  chosen.sort((a, b) => a.distance - b.distance);
  return chosen;
}

async function requestRoute(points: LatLon[]): Promise<TracedRoute | null> {
  const path = points.map((point) => `${point.lon.toFixed(6)},${point.lat.toFixed(6)}`).join(";");
  const url = `${ROUTER}/${path}?overview=full&geometries=geojson&steps=true`;
  let response: Response;
  try {
    response = await fetch(url, { signal: AbortSignal.timeout(12000) });
  } catch {
    throw new TraceError();
  }
  if (!response.ok) {
    if (response.status === 400) return null;
    throw new TraceError();
  }
  let body: OsrmResponse;
  try {
    body = (await response.json()) as OsrmResponse;
  } catch {
    throw new TraceError();
  }
  if (body.code === "NoRoute" || body.code === "NoSegment") return null;
  const route = body.routes?.[0];
  if (body.code !== "Ok" || !route) throw new TraceError();
  return parseRoute(route);
}

function parseRoute(route: OsrmRoute): TracedRoute | null {
  const coordinates = route.geometry?.coordinates ?? [];
  if (coordinates.length < 2) return null;
  const geometry = coordinates.map(([lon, lat]) => [round6(lat), round6(lon)] as [number, number]);
  const steps: TracedStep[] = [];
  for (const leg of route.legs ?? []) {
    for (const step of leg.steps ?? []) {
      const raw = step.geometry?.coordinates ?? [];
      if (raw.length < 2) continue;
      const name = (step.name ?? "").trim();
      const line = raw.map(([lon, lat]) => [round6(lat), round6(lon)] as [number, number]);
      const previous = steps[steps.length - 1];
      if (previous && name && previous.name === name) {
        previous.distance += step.distance;
        previous.geometry = previous.geometry.concat(line.slice(1));
      } else {
        steps.push({ name, distance: step.distance, geometry: line });
      }
    }
  }
  return { distance: route.distance, geometry, steps };
}

function offsetPoint(origin: LatLon, destination: LatLon, offsetM: number): LatLon {
  const midLat = (origin.lat + destination.lat) / 2;
  const metersPerLat = 111_320;
  const metersPerLon = 111_320 * Math.cos((midLat * Math.PI) / 180);
  const dx = (destination.lon - origin.lon) * metersPerLon;
  const dy = (destination.lat - origin.lat) * metersPerLat;
  const length = Math.hypot(dx, dy) || 1;
  return {
    lat: round6(midLat + ((dx / length) * offsetM) / metersPerLat),
    lon: round6((origin.lon + destination.lon) / 2 + ((-dy / length) * offsetM) / metersPerLon),
  };
}

function corridorsDiffer(a: [number, number][], b: [number, number][]): boolean {
  const step = Math.max(1, Math.floor(b.length / 20));
  let far = 0;
  for (let index = 0; index < b.length; index += step) {
    if (nearestMeters(b[index], a) > 70) far += 1;
  }
  return far >= 2;
}

function nearestMeters(point: [number, number], line: [number, number][]): number {
  const stride = Math.max(1, Math.floor(line.length / 48));
  let best = Infinity;
  for (let index = 0; index < line.length; index += stride) {
    best = Math.min(best, haversine(point, line[index]));
  }
  return best;
}

function haversine(a: [number, number], b: [number, number]): number {
  const radius = 6_371_000;
  const p1 = (a[0] * Math.PI) / 180;
  const p2 = (b[0] * Math.PI) / 180;
  const dp = ((b[0] - a[0]) * Math.PI) / 180;
  const dl = ((b[1] - a[1]) * Math.PI) / 180;
  const h = Math.sin(dp / 2) ** 2 + Math.cos(p1) * Math.cos(p2) * Math.sin(dl / 2) ** 2;
  return 2 * radius * Math.asin(Math.min(1, Math.sqrt(h)));
}

function round6(value: number): number {
  return Math.round(value * 1_000_000) / 1_000_000;
}
