// Owner: A4. Relay message types, taken from the generated OpenAPI types (via GET /api/_ws_schemas).
import type { components } from "../api/types.gen";

export type WalkerUpdate = components["schemas"]["WalkerUpdate"];
export type Envelope = components["schemas"]["Envelope"];
export type RelayMode = "e2ee" | "plaintext";
export type RelayStatus = "connecting" | "live" | "reconnecting" | "ended";
