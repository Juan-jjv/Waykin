import incidentsJson from "./fixtures/incidents.json";
import metaJson from "./fixtures/meta.json";
import { buildMockRoutes } from "./mockRoutes";

export { TraceError } from "./streetRoute";
import type {
  ErrorBody,
  ErrorCode,
  IncidentPoint,
  IncidentsResponse,
  Meta,
  RadiusM,
  RoutesRequest,
  RoutesResponse,
} from "./tmp-types";

const useMock = import.meta.env.VITE_USE_MOCK !== "0";
const metaFixture = metaJson as Meta;
const incidentPoints = incidentsJson.points as IncidentPoint[];

const ERROR_CODES = new Set<ErrorCode>([
  "outside_area",
  "no_path",
  "invalid_token",
  "expired",
  "not_found",
  "rate_limited",
  "forbidden",
  "validation",
]);

export class ApiError extends Error {
  readonly code: ErrorCode;

  constructor(code: ErrorCode, message: string) {
    super(message);
    this.name = "ApiError";
    this.code = code;
  }
}

export async function getMeta(): Promise<Meta> {
  if (useMock) return clone(metaFixture);
  const response = await fetch("/api/meta");
  if (!response.ok) throw await readError(response);
  return (await response.json()) as Meta;
}

export async function getIncidents(radiusM: RadiusM, categories: string[]): Promise<IncidentsResponse> {
  if (useMock) {
    const meta = clone(metaFixture);
    return {
      provenance: { ...meta.provenance, radius_m: radiusM },
      points: filterPoints(incidentPoints, categories),
    };
  }
  const params = new URLSearchParams({ radius_m: String(radiusM) });
  for (const category of categories) params.append("category", category);
  const response = await fetch(`/api/incidents?${params.toString()}`);
  if (!response.ok) throw await readError(response);
  return (await response.json()) as IncidentsResponse;
}

export async function planRoutes(request: RoutesRequest): Promise<RoutesResponse> {
  if (useMock) {
    try {
      return await buildMockRoutes(request);
    } catch (error) {
      if (isCoded(error) && error.code === "outside_area") {
        throw new ApiError("outside_area", "outside_area");
      }
      if (isCoded(error) && error.code === "no_path") {
        throw new ApiError("no_path", "no_path");
      }
      throw error;
    }
  }
  const response = await fetch("/api/routes", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(request),
  });
  if (!response.ok) throw await readError(response);
  return (await response.json()) as RoutesResponse;
}

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

async function readError(response: Response): Promise<ApiError> {
  try {
    const body = (await response.json()) as Partial<ErrorBody>;
    const code = body.error?.code;
    const message = body.error?.message ?? "Request failed";
    if (code && ERROR_CODES.has(code)) return new ApiError(code, message);
  } catch {
    /* Response was not the error model. */
  }
  return new ApiError("validation", "Request failed");
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
