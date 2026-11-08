import hashlib
import json
from datetime import timedelta

from fastapi import APIRouter, Depends, Query

from waykin import constants as C
from waykin import schemas as S
from waykin.api.deps import demo_presets, get_state, mock
from waykin.provenance import build_provenance

router = APIRouter()


def _thresholds() -> S.Thresholds:
    return S.Thresholds(min_reduction=C.MIN_REDUCTION, min_draw_share=C.MIN_DRAW_SHARE, max_extra_time=C.MAX_EXTRA_TIME)


@router.get("/meta", response_model=S.Meta)
def meta(state=Depends(get_state)) -> S.Meta:
    s = state.settings
    if s.WAYKIN_MOCK:
        m = S.Meta.model_validate(mock("meta"))
        return m.model_copy(update={"relay_mode": s.relay_mode, "demo_mode": s.DEMO_MODE,
                                    "demo_presets": m.demo_presets if s.DEMO_MODE else []})
    b = state.exposure
    return S.Meta(provenance=build_provenance(state, s.DEFAULT_RADIUS_M), radii=list(b.radii),
                  default_radius_m=s.DEFAULT_RADIUS_M, bbox=list(state.graph.bbox), categories=list(b.categories),
                  category_preset=b.category_preset, relay_mode=s.relay_mode, n_draws=C.N_DRAWS,
                  thresholds=_thresholds(), demo_mode=s.DEMO_MODE,
                  demo_presets=[S.DemoPreset.model_validate(p) for p in demo_presets()] if s.DEMO_MODE else [])


def _mock_age_days(location_id: str) -> int:
    """The mock fixture has no dates, so each point gets a fixed made-up age for the date filter."""
    return int.from_bytes(hashlib.blake2b(location_id.encode(), digest_size=2).digest(), "big") % C.WINDOW_DAYS


def _filter_categories(points: list[S.IncidentPoint], category: list[str] | None) -> list[S.IncidentPoint]:
    if not category:
        return points
    out = []
    for p in points:
        by = {k: v for k, v in p.by_category.items() if k in category}
        if by:
            out.append(p.model_copy(update={"by_category": by, "count": sum(by.values())}))
    return out


def _recent_points(state, days: int, category: list[str] | None) -> list[S.IncidentPoint]:
    """Points from the per-day table: reports on the last `days` days up to as_of."""
    b = state.exposure
    d = b.daily
    d = d[d["date"] > b.as_of - timedelta(days=days)]
    if category:
        d = d[d["category"].isin(category)]
    by_location: dict[str, dict[str, int]] = {}
    for (location_id, cat), n in d.groupby(["location_id", "category"])["count"].sum().items():
        by_location.setdefault(location_id, {})[cat] = int(n)
    where = b.locations.set_index("location_id")
    return [S.IncidentPoint(location_id=lid, lat=float(where.at[lid, "lat"]), lon=float(where.at[lid, "lon"]),
                            count=sum(by.values()), by_category=dict(sorted(by.items())))
            for lid, by in sorted(by_location.items()) if lid in where.index]


@router.get("/incidents", response_model=S.IncidentsResponse)
def incidents(radius_m: int | None = None, category: list[str] | None = Query(default=None),
              days: int | None = Query(default=None, ge=1, le=C.WINDOW_DAYS),
              state=Depends(get_state)) -> S.IncidentsResponse:
    s = state.settings
    if s.WAYKIN_MOCK:
        r = S.IncidentsResponse.model_validate(mock("incidents"))
        pts = _filter_categories(r.points, category)
        if days:
            pts = [p for p in pts if _mock_age_days(p.location_id) < days]
            return S.IncidentsResponse(provenance=r.provenance.model_copy(update={"window_days": days}), points=pts)
        return r.model_copy(update={"points": pts})
    radius = radius_m if radius_m in state.exposure.radii else s.DEFAULT_RADIUS_M
    provenance = build_provenance(state, radius)
    if days and state.exposure.daily is not None:
        return S.IncidentsResponse(provenance=provenance.model_copy(update={"window_days": days}),
                                   points=_recent_points(state, days, category))
    provenance = provenance.model_copy(update={"window_days": C.WINDOW_DAYS})
    pts = []
    for row in state.exposure.locations.itertuples(index=False):
        by = json.loads(row.counts_by_category) if row.counts_by_category else {}
        if category:
            by = {k: v for k, v in by.items() if k in category}
            if not by:
                continue
        pts.append(S.IncidentPoint(location_id=row.location_id, lat=float(row.lat), lon=float(row.lon),
                                   count=int(sum(by.values())) if category else int(row.count), by_category=by))
    return S.IncidentsResponse(provenance=provenance, points=pts)


@router.get("/_ws_schemas", response_model=S.WsSchemas)
def ws_schemas() -> S.WsSchemas:
    """Exists only so WebSocket message types appear in OpenAPI."""
    return S.WsSchemas()
