"""API v1 models (B5). Frozen at H3: change only through contract-requests/.

Request models use extra="forbid". TypeScript types are generated from /openapi.json.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from waykin import constants as C

# ---------------------------------------------------------------- literals
RouteLabelOut = Literal["fastest", "balanced", "lower_exposure"]
AbstainReason = Literal["thin_data", "indistinguishable", "too_costly", "no_alternative"]
DecisionStatus = Literal["recommend", "abstain"]
ErrorCode = Literal[
    "outside_area", "no_path", "invalid_token", "expired", "not_found", "rate_limited", "forbidden", "validation"
]
RelayMode = Literal["e2ee", "plaintext"]
Role = Literal["walker", "viewer"]
HazardKind = Literal["closure", "incident", "report"]
HazardSource = Literal["demo", "manual", "city_feed"]
SourceName = Literal["eps", "synthetic"]
RadiusM = Literal[50, 100, 200]
PresetExpected = Literal["recommend", "abstain", "reroute"]
WalkerStatus = Literal["walking", "rerouted", "arrived"]
EndReason = Literal["arrived", "stopped"]
EndedReason = Literal["arrived", "stopped", "expired"]

LatLonPair = tuple[float, float]  # [lat, lon]


class _Request(BaseModel):
    model_config = ConfigDict(extra="forbid")


# ---------------------------------------------------------------- common
class LatLon(_Request):
    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)


class Provenance(BaseModel):
    source: SourceName
    source_label: str
    as_of: date
    window_days: int
    radius_m: int
    units: str = C.UNITS
    disclaimer: str = C.DISCLAIMER


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


class Thresholds(BaseModel):
    min_reduction: float = C.MIN_REDUCTION
    min_draw_share: float = C.MIN_DRAW_SHARE
    max_extra_time: float = C.MAX_EXTRA_TIME


# ---------------------------------------------------------------- meta
class DemoPreset(BaseModel):
    id: str
    name: str
    description: str
    origin: LatLon
    destination: LatLon
    expected: PresetExpected


class Meta(BaseModel):
    api_version: Literal["1"] = "1"
    provenance: Provenance
    radii: list[int]
    default_radius_m: int
    bbox: list[float] = Field(min_length=4, max_length=4, description="[west, south, east, north]")
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
class RoutesRequest(_Request):
    origin: LatLon
    destination: LatLon
    radius_m: RadiusM | None = None


class RerouteRequest(_Request):
    """No journey id, no token, no cookies. The server cannot link it to a person."""

    position: LatLon
    destination: LatLon
    radius_m: RadiusM | None = None


class TopSegment(BaseModel):
    edge_id: int
    name: str | None
    attributed: float
    geometry: list[LatLonPair]


class RouteOption(BaseModel):
    route_id: str
    label: RouteLabelOut
    minutes: float
    extra_minutes: float
    distance_m: float
    exposure: Interval
    exposure_diff_vs_fastest: Interval | None
    draws_better: int | None
    geometry: list[LatLonPair]
    edge_ids: list[int]
    top_segments: list[TopSegment] = Field(max_length=3)
    explanation: str


class Decision(BaseModel):
    status: DecisionStatus
    recommended_route_id: str | None
    reason: AbstainReason | None
    message: str
    radius_sensitive: bool | None
    radius_decisions: dict[str, str] | None
    thresholds: Thresholds = Field(default_factory=Thresholds)
    n_draws: int = C.N_DRAWS


class RoutesResponse(BaseModel):
    provenance: Provenance
    origin_snapped: LatLon
    destination_snapped: LatLon
    routes: list[RouteOption]
    decision: Decision
    blocked_edge_count: int


# ---------------------------------------------------------------- journeys
class JourneyCreate(_Request):
    expires_in_min: int | None = Field(
        default=None, ge=10, le=C.JOURNEY_TTL_MIN_MAX, description="Defaults to JOURNEY_TTL_MIN (120)."
    )


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
    source: HazardSource
    created_at: datetime
    expires_at: datetime
    edge_ids: list[int]


class HazardCreate(_Request):
    kind: HazardKind
    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)
    radius_m: float = Field(default=40, ge=10, le=300)
    ttl_min: int = Field(default=60, ge=1, le=720)
    description: str = Field(max_length=140)


class HazardList(BaseModel):
    hazards: list[Hazard]
    blocked_edge_ids: list[int]


# ---------------------------------------------------------------- relay WebSocket messages
class Envelope(BaseModel):
    v: Literal[1] = 1
    seq: int = Field(description="strictly increasing")
    iv: str = Field(description="base64url, 12 bytes, no padding")
    ct: str = Field(description="base64url AES-GCM ciphertext + tag, no padding")


class RouteRef(BaseModel):
    route_id: str
    label: RouteLabelOut
    geometry: list[LatLonPair]


class WalkerUpdate(BaseModel):
    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)
    accuracy_m: float
    ts: int = Field(description="ms since epoch")
    status: WalkerStatus
    eta_min: float
    route: RouteRef | None = None
    note: str | None = None


class WsAuth(BaseModel):
    type: Literal["auth"] = "auth"
    role: Role
    token: str


class WsReady(BaseModel):
    type: Literal["ready"] = "ready"
    relay_mode: RelayMode
    expires_at: datetime


class WsLoc(BaseModel):
    type: Literal["loc"] = "loc"
    env: Envelope | None = Field(default=None, description="e2ee mode")
    plain: WalkerUpdate | None = Field(default=None, description="plaintext mode")


class WsEnd(BaseModel):
    type: Literal["end"] = "end"
    reason: EndReason


class WsEnded(BaseModel):
    type: Literal["ended"] = "ended"
    reason: EndedReason


class WsPing(BaseModel):
    type: Literal["ping"] = "ping"


# ---------------------------------------------------------------- hazard stream messages
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


class WsSchemas(BaseModel):
    """Exists only so WebSocket message types appear in OpenAPI (and types.gen.ts)."""

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


# ---------------------------------------------------------------- demo presets file (internal)
class PresetHazard(BaseModel):
    lat: float
    lon: float
    radius_m: float = 40
    description: str


class DemoPresetFile(DemoPreset):
    hazard: PresetHazard | None = None
