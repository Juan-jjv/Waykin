"""GET /api/incidents: only the source's published intersection-level points."""

from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, Query

from waykin import mocks
from waykin.api.deps import StateDep
from waykin.api.errors import ApiError
from waykin.provenance import build_provenance
from waykin.schemas import IncidentPoint, IncidentsResponse, RadiusM
from waykin.state import AppState

router = APIRouter(tags=["incidents"])

_cache: dict[int, list[dict[str, Any]]] = {}


def _points_from_bundle(state: AppState) -> list[dict[str, Any]]:
    df = state.exposure.locations
    key = id(df)
    if key not in _cache:
        _cache.clear()
        pts = []
        for row in df.itertuples(index=False):
            cbc = row.counts_by_category
            by_cat = json.loads(cbc) if isinstance(cbc, str | bytes) else dict(cbc or {})
            pts.append({
                "location_id": str(row.location_id),
                "lat": float(row.lat),
                "lon": float(row.lon),
                "count": int(row.count),
                "by_category": {str(k): int(v) for k, v in by_cat.items()},
            })
        _cache[key] = pts
    return _cache[key]


def _filter(points: list[dict[str, Any]], categories: list[str] | None) -> list[IncidentPoint]:
    out = []
    for p in points:
        if categories:
            by_cat = {c: n for c, n in p["by_category"].items() if c in categories and n > 0}
            count = sum(by_cat.values())
            if count <= 0:
                continue
        else:
            by_cat, count = p["by_category"], p["count"]
        out.append(IncidentPoint(location_id=p["location_id"], lat=p["lat"], lon=p["lon"],
                                 count=count, by_category=by_cat))
    return out


@router.get("/incidents", response_model=IncidentsResponse)
async def get_incidents(
    radius_m: RadiusM | None = Query(default=None),
    category: list[str] | None = Query(default=None),
    state: AppState = StateDep,
) -> IncidentsResponse:
    r = radius_m or state.settings.DEFAULT_RADIUS_M
    if state.mock:
        points = mocks.load("incidents")["points"]
    else:
        if r not in state.exposure.radii:
            raise ApiError(422, "validation", "That radius is not loaded on this server.")
        points = _points_from_bundle(state)
    return IncidentsResponse(provenance=build_provenance(state, r), points=_filter(points, category))
