// Friendly aliases over the GENERATED types. Never edit types.gen.ts by hand: run `npm run gen:types`.
import type { components } from "./types.gen";

type S = components["schemas"];

export type Meta = S["Meta"];
export type Provenance = S["Provenance"];
export type LatLon = S["LatLon"];
export type RoutesRequest = S["RoutesRequest"];
export type RerouteRequest = S["RerouteRequest"];
export type RoutesResponse = S["RoutesResponse"];
export type RouteOption = S["RouteOption"];
export type Decision = S["Decision"];
export type IncidentsResponse = S["IncidentsResponse"];
export type IncidentPoint = S["IncidentPoint"];
export type JourneyCreated = S["JourneyCreated"];
export type Hazard = S["Hazard"];
export type HazardList = S["HazardList"];
export type DemoPreset = S["DemoPreset"];
export type ErrorCode =
  | "outside_area" | "no_path" | "invalid_token" | "expired" | "not_found" | "rate_limited" | "forbidden" | "validation";
export type AbstainReason = NonNullable<Decision["reason"]>;
