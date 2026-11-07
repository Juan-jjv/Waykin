// Local mirrors of the B5 relay types. Once src/api/types.gen.ts exists these must stay
// structurally identical to components["schemas"]["WalkerUpdate"] / ["Envelope"].

export type RelayMode = "e2ee" | "plaintext";
export type RelayStatus = "connecting" | "live" | "reconnecting" | "ended";
export type RouteLabel = "fastest" | "balanced" | "lower_exposure";
export type LatLonPair = [number, number];

export interface Envelope {
  v: 1;
  seq: number; // strictly increasing
  iv: string; // base64url, 12 bytes, no padding
  ct: string; // base64url, AES-GCM ciphertext + tag, no padding
}

export interface WalkerUpdate {
  lat: number;
  lon: number;
  accuracy_m: number;
  ts: number; // ms epoch
  status: "walking" | "rerouted" | "arrived";
  eta_min: number;
  route?: { route_id: string; label: RouteLabel; geometry: LatLonPair[] } | null;
  note?: string | null;
}

export interface GeoFix {
  lat: number;
  lon: number;
  accuracy_m: number;
  ts: number;
}
