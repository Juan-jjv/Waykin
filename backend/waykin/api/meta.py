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
                  default_radius_m=s.DEFAULT_RADIUS_M, bbox=list(C.DEMO_BBOX), categories=list(b.categories),
                  category_preset=b.category_preset, relay_mode=s.relay_mode, n_draws=C.N_DRAWS,
                  thresholds=_thresholds(), demo_mode=s.DEMO_MODE,
                  demo_presets=[S.DemoPreset.model_validate(p) for p in demo_presets()] if s.DEMO_MODE else [])


@router.get("/incidents", response_model=S.IncidentsResponse)
def incidents(radius_m: int | None = None, category: list[str] | None = Query(default=None),
              state=Depends(get_state)) -> S.IncidentsResponse:
    import json

    s = state.settings
    if s.WAYKIN_MOCK:
        r = S.IncidentsResponse.model_validate(mock("incidents"))
        if category:
            pts = []
            for p in r.points:
                by = {k: v for k, v in p.by_category.items() if k in category}
                if by:
                    pts.append(p.model_copy(update={"by_category": by, "count": sum(by.values())}))
            r = r.model_copy(update={"points": pts})
        return r
    radius = radius_m if radius_m in state.exposure.radii else s.DEFAULT_RADIUS_M
    pts = []
    for row in state.exposure.locations.itertuples(index=False):
        by = json.loads(row.counts_by_category) if row.counts_by_category else {}
        if category:
            by = {k: v for k, v in by.items() if k in category}
            if not by:
                continue
        pts.append(S.IncidentPoint(location_id=row.location_id, lat=float(row.lat), lon=float(row.lon),
                                   count=int(sum(by.values())) if category else int(row.count), by_category=by))
    return S.IncidentsResponse(provenance=build_provenance(state, radius), points=pts)


@router.get("/_ws_schemas", response_model=S.WsSchemas)
def ws_schemas() -> S.WsSchemas:
    """Exists only so WebSocket message types appear in OpenAPI."""
    return S.WsSchemas()
