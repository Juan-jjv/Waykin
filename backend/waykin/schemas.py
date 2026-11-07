"""API contract v1 (spec B5). Frozen at H10: change only through contract-requests/ and APPLIED.md."""
from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

RouteLabelOut = Literal["fastest", "balanced", "lower_exposure"]
AbstainReason = Literal["thin_data", "indistinguishable", "too_costly", "no_alternative"]
ErrorCode = Literal["outside_area", "no_path", "invalid_token", "expired", "not_found",
                    "rate_limited", "forbidden", "validation"]
RelayMode = Literal["e2ee", "plaintext"]
HazardKind = Literal["closure", "incident", "report"]
Radius = Literal[50, 100, 200]


class Request(BaseModel):
    model_config = ConfigDict(extra="forbid")


# ---------------------------------------------------------------- common
class LatLon(BaseModel):
    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)


class LatLonIn(Request):
    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)


class Provenance(BaseModel):
    source: Literal["eps", "synthetic"]
    source_label: str
    as_of: date
    window_days: int
    radius_m: int
    units: str
    disclaimer: str


class Interval(BaseModel):
    p10: float
    p50: float
    p90: float
    mean: float


class ErrorBody(BaseModel):
    code: ErrorCode
    message: str


class Error(BaseModel):
    error: ErrorBody


# ---------------------------------------------------------------- meta
class Thresholds(BaseModel):
    min_reduction: float
    min_draw_share: float
    max_extra_time: float


class DemoPreset(BaseModel):
    id: str
    name: str
    description: str
    origin: LatLon
    destination: LatLon
    expected: Literal["recommend", "abstain", "reroute"]


class Meta(BaseModel):
    api_version: Literal["1"] = "1"
    provenance: Provenance
    radii: list[int]
    default_radius_m: int
    bbox: list[float]
    categories: list[str]
    category_preset: str
    relay_mode: RelayMode
    n_draws: int
    thresholds: Thresholds
    demo_mode: bool
    demo_presets: list[DemoPreset]


# ---------------------------------------------------------------- incidents
class IncidentPoint(BaseModel):
    location_id: str
    lat: float
    lon: float
    count: int
    by_category: dict[str, int]


class IncidentsResponse(BaseModel):
    provenance: Provenance
    points: list[IncidentPoint]


# ---------------------------------------------------------------- routes
class RoutesRequest(Request):
    origin: LatLonIn
    destination: LatLonIn
    radius_m: Radius | None = None


class RerouteRequest(Request):
    """No journey id, no token, no cookies: the server cannot link it to a person."""
    position: LatLonIn
    destination: LatLonIn
    radius_m: Radius | None = None


class TopSegment(BaseModel):
    edge_id: int
    name: str | None
    attributed: float
    geometry: list[list[float]]


class RouteOption(BaseModel):
    route_id: str
    label: RouteLabelOut
    minutes: float
    extra_minutes: float
    distance_m: float
    exposure: Interval
    exposure_diff_vs_fastest: Interval | None
    draws_better: int | None
    geometry: list[list[float]]
    edge_ids: list[int]
    top_segments: list[TopSegment]
    explanation: str


class Decision(BaseModel):
    status: Literal["recommend", "abstain"]
    recommended_route_id: str | None
    reason: AbstainReason | None
    message: str
    radius_sensitive: bool | None
    radius_decisions: dict[str, str] | None
    thresholds: Thresholds
    n_draws: int


class RoutesResponse(BaseModel):
    provenance: Provenance
    origin_snapped: LatLon
    destination_snapped: LatLon
    routes: list[RouteOption]
    decision: Decision
    blocked_edge_count: int


# ---------------------------------------------------------------- journeys
class JourneyCreate(Request):
    expires_in_min: int = Field(default=120, ge=10, le=240)


class JourneyCreated(BaseModel):
    journey_id: str
    walker_token: str
    viewer_token: str
    expires_at: datetime
    relay_mode: RelayMode


# ---------------------------------------------------------------- hazards
class Hazard(BaseModel):
    hazard_id: str
    kind: HazardKind
    lat: float
    lon: float
    radius_m: float
    description: str
    source: Literal["demo", "manual", "city_feed"]
    created_at: datetime
    expires_at: datetime
    edge_ids: list[int]


class HazardCreate(Request):
    kind: HazardKind = "closure"
    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)
    radius_m: float = Field(default=40, ge=10, le=300)
    ttl_min: int = Field(default=60, ge=1, le=720)
    description: str = Field(default="Closure", max_length=140)


class HazardList(BaseModel):
    hazards: list[Hazard]
    blocked_edge_ids: list[int]


# ---------------------------------------------------------------- WebSocket messages (relay + hazard stream)
class Envelope(BaseModel):
    v: Literal[1] = 1
    seq: int
    iv: str
    ct: str


class RouteRef(BaseModel):
    route_id: str
    label: RouteLabelOut
    geometry: list[list[float]]


class WalkerUpdate(BaseModel):
    lat: float
    lon: float
    accuracy_m: float
    ts: int
    status: Literal["walking", "rerouted", "arrived"]
    eta_min: float
    route: RouteRef | None = None
    note: str | None = None


class WsAuth(BaseModel):
    type: Literal["auth"] = "auth"
    role: Literal["walker", "viewer"]
    token: str


class WsReady(BaseModel):
    type: Literal["ready"] = "ready"
    relay_mode: RelayMode
    expires_at: datetime


class WsLoc(BaseModel):
    type: Literal["loc"] = "loc"
    env: Envelope | None = None
    plain: WalkerUpdate | None = None


class WsEnd(BaseModel):
    type: Literal["end"] = "end"
    reason: Literal["arrived", "stopped"]


class WsEnded(BaseModel):
    type: Literal["ended"] = "ended"
    reason: Literal["arrived", "stopped", "expired"]


class HazardSnapshot(BaseModel):
    type: Literal["snapshot"] = "snapshot"
    hazards: list[Hazard]
    blocked_edge_ids: list[int]


class HazardAdded(BaseModel):
    type: Literal["hazard.added"] = "hazard.added"
    hazard: Hazard


class HazardRemoved(BaseModel):
    type: Literal["hazard.removed"] = "hazard.removed"
    hazard_id: str
    edge_ids: list[int]


class WsPing(BaseModel):
    type: Literal["ping"] = "ping"


class WsSchemas(BaseModel):
    """Exists only so the WebSocket message models appear in OpenAPI for type generation."""
    auth: WsAuth | None = None
    ready: WsReady | None = None
    loc: WsLoc | None = None
    end: WsEnd | None = None
    ended: WsEnded | None = None
    envelope: Envelope | None = None
    walker_update: WalkerUpdate | None = None
    hazard_snapshot: HazardSnapshot | None = None
    hazard_added: HazardAdded | None = None
    hazard_removed: HazardRemoved | None = None
    ping: WsPing | None = None
