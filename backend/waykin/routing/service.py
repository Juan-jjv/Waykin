"""The single orchestration function used by routes and reroute endpoints."""

from __future__ import annotations

import numpy as np

from waykin import constants as C, schemas as S
from waykin.data.stability import assess
from waykin.provenance import build_provenance
from waykin.routing.explain import explanation_text, route_geometry, top_segments
from waykin.routing.router import candidate_set
from waykin.routing.types import NoPathError


def plan(state, origin: S.LatLon, destination: S.LatLon, radius_m: int) -> S.RoutesResponse:
    graph = state.graph
    bundle = state.exposure
    if radius_m not in bundle.radii:
        radius_m = state.settings.DEFAULT_RADIUS_M
    if radius_m not in bundle.radii:
        raise ValueError("default exposure radius is not loaded")

    src, _ = graph.snap(origin.lat, origin.lon)
    dst, _ = graph.snap(destination.lat, destination.lon)
    if src == dst:
        raise NoPathError("same_point")

    blocked = np.asarray(state.hazards.blocked_mask(), dtype=bool)
    candidates = candidate_set(graph, bundle.mean[radius_m], src, dst, blocked)
    assessment = assess(candidates, bundle, radius_m)
    chosen = [candidates.fastest, *candidates.alternatives]
    options: list[S.RouteOption] = []

    for route in chosen:
        stats = assessment.stats[route.route_id]
        diff = None
        if stats.diff_p10 is not None:
            diff = S.Interval(p10=stats.diff_p10, p50=stats.diff_p50, p90=stats.diff_p90, mean=stats.diff_mean)
        options.append(S.RouteOption(
            route_id=route.route_id,
            label=route.label,
            minutes=route.minutes,
            extra_minutes=max(0.0, route.minutes - candidates.fastest.minutes),
            distance_m=route.distance_m,
            exposure=S.Interval(p10=stats.p10, p50=stats.p50, p90=stats.p90, mean=stats.mean),
            exposure_diff_vs_fastest=diff,
            draws_better=stats.draws_better,
            geometry=route_geometry(graph, route.node_ids, route.edge_ids),
            edge_ids=route.edge_ids.tolist(),
            top_segments=top_segments(graph, route.edge_ids, bundle.mean[radius_m], k=3),
            explanation=explanation_text(route.label, route.minutes,
                                         max(0.0, route.minutes - candidates.fastest.minutes),
                                         stats.diff_p50, stats.p50),
        ))

    decision = S.Decision(
        status=assessment.status,
        recommended_route_id=assessment.recommended_route_id,
        reason=assessment.reason,
        message=assessment.message,
        radius_sensitive=assessment.radius_sensitive,
        radius_decisions={str(k): v for k, v in assessment.radius_decisions.items()}
        if assessment.radius_decisions is not None else None,
        thresholds=S.Thresholds(
            min_reduction=C.MIN_REDUCTION,
            min_draw_share=C.MIN_DRAW_SHARE,
            max_extra_time=C.MAX_EXTRA_TIME,
        ),
        n_draws=C.N_DRAWS,
    )
    return S.RoutesResponse(
        provenance=build_provenance(state, radius_m),
        origin_snapped=S.LatLon(lat=float(graph.node_lat[src]), lon=float(graph.node_lon[src])),
        destination_snapped=S.LatLon(lat=float(graph.node_lat[dst]), lon=float(graph.node_lon[dst])),
        routes=options,
        decision=decision,
        blocked_edge_count=int(blocked.sum()),
    )
