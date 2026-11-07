export interface LatLon {
  lat: number;
  lon: number;
}

export interface Provenance {
  source: "eps" | "synthetic";
  source_label: string;
  as_of: string;
  window_days: number;
  radius_m: number;
  units: string;
  disclaimer: string;
}

export interface DemoPreset {
  id: string;
  name: string;
  description: string;
  origin: LatLon;
  destination: LatLon;
  expected: "recommend" | "abstain" | "reroute";
}

export interface Thresholds {
  min_reduction: number;
  min_draw_share: number;
  max_extra_time: number;
}

export interface Meta {
  api_version: "1";
  provenance: Provenance;
  radii: RadiusM[];
  default_radius_m: RadiusM;
  bbox: BBox;
  categories: string[];
  category_preset: string;
  relay_mode: "e2ee" | "plaintext";
  n_draws: number;
  thresholds: Thresholds;
  demo_mode: boolean;
  demo_presets: DemoPreset[];
}

export type BBox = [west: number, south: number, east: number, north: number];
export type RadiusM = 50 | 100 | 200;
export type RouteLabel = "fastest" | "balanced" | "lower_exposure";
export type AbstainReason = "thin_data" | "indistinguishable" | "too_costly" | "no_alternative";
export type ErrorCode =
  | "outside_area"
  | "no_path"
  | "invalid_token"
  | "expired"
  | "not_found"
  | "rate_limited"
  | "forbidden"
  | "validation";

export interface IncidentPoint {
  location_id: string;
  lat: number;
  lon: number;
  count: number;
  by_category: Record<string, number>;
}

export interface IncidentsResponse {
  provenance: Provenance;
  points: IncidentPoint[];
}

export interface Interval {
  p10: number;
  p50: number;
  p90: number;
  mean: number;
}

export interface TopSegment {
  edge_id: number;
  name: string | null;
  attributed: number;
  geometry: [number, number][];
}

export interface RouteOption {
  route_id: string;
  label: RouteLabel;
  minutes: number;
  extra_minutes: number;
  distance_m: number;
  exposure: Interval;
  exposure_diff_vs_fastest: Interval | null;
  draws_better: number | null;
  geometry: [number, number][];
  edge_ids: number[];
  top_segments: TopSegment[];
  explanation: string;
}

export interface Decision {
  status: "recommend" | "abstain";
  recommended_route_id: string | null;
  reason: AbstainReason | null;
  message: string;
  radius_sensitive: boolean | null;
  radius_decisions: Record<string, string> | null;
  thresholds: Thresholds;
  n_draws: number;
}

export interface RoutesRequest {
  origin: LatLon;
  destination: LatLon;
  radius_m?: RadiusM;
}

export interface RoutesResponse {
  provenance: Provenance;
  origin_snapped: LatLon;
  destination_snapped: LatLon;
  routes: RouteOption[];
  decision: Decision;
  blocked_edge_count: number;
}

export interface ErrorBody {
  error: {
    code: ErrorCode;
    message: string;
  };
}
