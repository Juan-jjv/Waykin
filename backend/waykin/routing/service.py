"""The only function the /routes and /routes/reroute endpoints call (spec A3.6).

Phase 1 stub: a straight-line "fastest" route with an abstain(no_alternative) decision, so the
frontend and API can integrate early. Phase 2 replaces the body with snap → candidate_set → assess → explain.
Never logs the inputs or the snapped coordinates.
"""
from __future__ import annotations

import math

from waykin import constants as C
from waykin import schemas
from waykin.provenance import build_provenance
from waykin.routing.explain import explanation_text
from waykin.routing.types import NoPathError


def _thresholds() -> schemas.Thresholds:
    return schemas.Thresholds(min_reduction=C.MIN_REDUCTION, min_draw_share=C.MIN_DRAW_SHARE,
                              max_extra_time=C.MAX_EXTRA_TIME)


def plan(state, origin: schemas.LatLon, destination: schemas.LatLon, radius_m: int) -> schemas.RoutesResponse:
    graph = state.graph
    if radius_m not in (state.exposure.radii if state.exposure is not None else [radius_m]):
        radius_m = state.settings.DEFAULT_RADIUS_M
    src, _ = graph.snap(origin.lat, origin.lon)
    dst, _ = graph.snap(destination.lat, destination.lon)
    if src == dst:
        raise NoPathError("same_point")
    a = (float(graph.node_lat[src]), float(graph.node_lon[src]))
    b = (float(graph.node_lat[dst]), float(graph.node_lon[dst]))
    dist = math.dist(graph.to_utm(*a), graph.to_utm(*b))
    minutes = dist / C.WALK_SPEED_M_PER_MIN
    zero = schemas.Interval(p10=0.0, p50=0.0, p90=0.0, mean=0.0)
    route = schemas.RouteOption(
        route_id="stub-route", label="fastest", minutes=round(minutes, 1), extra_minutes=0.0,
        distance_m=round(dist, 1), exposure=zero, exposure_diff_vs_fastest=None, draws_better=None,
        geometry=[list(a), list(b)], edge_ids=[], top_segments=[],
        explanation=explanation_text("fastest", minutes, 0.0, None, 0.0),
    )
    decision = schemas.Decision(
        status="abstain", recommended_route_id=None, reason="no_alternative",
        message="There is only one reasonable route for this trip.",
        radius_sensitive=None, radius_decisions=None, thresholds=_thresholds(), n_draws=C.N_DRAWS,
    )
    return schemas.RoutesResponse(
        provenance=build_provenance(state, radius_m),
        origin_snapped=schemas.LatLon(lat=a[0], lon=a[1]), destination_snapped=schemas.LatLon(lat=b[0], lon=b[1]),
        routes=[route], decision=decision, blocked_edge_count=0,
    )
