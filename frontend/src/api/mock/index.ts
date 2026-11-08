// In-browser mock (VITE_USE_MOCK=1): follows real streets via OSRM, with made-up exposure numbers.
import { ApiError } from "../client";
import type { IncidentPoint, IncidentsResponse, Meta, RoutesRequest, RoutesResponse } from "../types";
import incidentsJson from "./fixtures/incidents.json";
import metaJson from "./fixtures/meta.json";
import { buildMockRoutes } from "./mockRoutes";

const metaFixture = metaJson as Meta;
const incidentPoints = incidentsJson.points as IncidentPoint[];

export const mockApi = {
  meta: async (): Promise<Meta> => clone(metaFixture),

  incidents: async (radius_m: number, categories: string[], days: number): Promise<IncidentsResponse> => {
    const meta = clone(metaFixture);
    return {
      provenance: { ...meta.provenance, radius_m, window_days: days },
      points: filterPoints(incidentPoints, categories).filter((point) => mockAgeDays(point.location_id) < days),
    };
  },

  routes: async (req: RoutesRequest): Promise<RoutesResponse> => {
    try {
      return await buildMockRoutes(req);
    } catch (error) {
      if (isCoded(error)) throw new ApiError(422, error.code, error.code);
      throw error;
    }
  },
};

function filterPoints(points: IncidentPoint[], categories: string[]): IncidentPoint[] {
  return points.flatMap((point) => {
    const byCategory: Record<string, number> = {};
    let count = 0;
    for (const category of categories) {
      const value = point.by_category[category] ?? 0;
      if (value > 0) {
        byCategory[category] = value;
        count += value;
      }
    }
    if (count <= 0) return [];
    return [{ ...point, count, by_category: byCategory }];
  });
}

/** The fixture has no dates, so each point gets a fixed made-up age for the date filter. */
function mockAgeDays(id: string): number {
  let hash = 0;
  for (const char of id) hash = (hash * 31 + char.charCodeAt(0)) >>> 0;
  return hash % 90;
}

function isCoded(error: unknown): error is { code: "outside_area" | "no_path" } {
  return (
    typeof error === "object" &&
    error !== null &&
    "code" in error &&
    (error.code === "outside_area" || error.code === "no_path")
  );
}

function clone<T>(value: T): T {
  return JSON.parse(JSON.stringify(value)) as T;
}
