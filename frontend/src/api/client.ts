import type {
  ErrorCode, HazardList, IncidentsResponse, JourneyCreated, Meta, RerouteRequest, RoutesRequest, RoutesResponse,
} from "./types";

export { TraceError } from "./mock/streetRoute";

export class ApiError extends Error {
  constructor(public status: number, public code: ErrorCode | "network", message: string) {
    super(message);
  }
}

const USE_MOCK = import.meta.env.VITE_USE_MOCK === "1";
const mock = () => import("./mock").then((m) => m.mockApi);

async function call<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`/api${path}`, {
      ...init,
      headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
    });
  } catch {
    throw new ApiError(0, "network", "Can't reach the WayKin server");
  }
  if (res.status === 204) return undefined as T;
  const body = await res.json().catch(() => null);
  if (!res.ok) {
    const err = body?.error;
    throw new ApiError(res.status, err?.code ?? "validation", err?.message ?? `HTTP ${res.status}`);
  }
  return body as T;
}

export const api = {
  meta: () => (USE_MOCK ? mock().then((m) => m.meta()) : call<Meta>("/meta")),
  incidents: (radius_m: number, categories: string[], days: number) => {
    if (USE_MOCK) return mock().then((m) => m.incidents(radius_m, categories, days));
    const q = new URLSearchParams({ radius_m: String(radius_m), days: String(days) });
    categories.forEach((c) => q.append("category", c));
    return call<IncidentsResponse>(`/incidents?${q}`);
  },
  routes: (req: RoutesRequest) =>
    USE_MOCK ? mock().then((m) => m.routes(req)) : call<RoutesResponse>("/routes", { method: "POST", body: JSON.stringify(req) }),
  reroute: (req: RerouteRequest) => call<RoutesResponse>("/routes/reroute", { method: "POST", body: JSON.stringify(req) }),
  createJourney: (expires_in_min?: number) =>
    call<JourneyCreated>("/journeys", { method: "POST", body: JSON.stringify(expires_in_min ? { expires_in_min } : {}) }),
  endJourney: (id: string, walkerToken: string) =>
    call<void>(`/journeys/${encodeURIComponent(id)}`, { method: "DELETE", headers: { Authorization: `Bearer ${walkerToken}` } }),
  hazards: () => call<HazardList>("/hazards"),
};
