"""The single orchestration function used by routes and reroute endpoints."""

from __future__ import annotations

import numpy as np

from waykin import constants as C, schemas as S
from waykin.data.stability import assess
from waykin.data.walk_pressure import walk_pressure_for
from waykin.provenance import build_provenance
from waykin.routing.explain import explanation_text, route_geometry, top_segments
from waykin.routing.router import candidate_set
from waykin.routing.types import NoPathError, TravelMode


def avoid_message(fastest_m: float, lower_m: float, extra_min: float) -> str:
    serious = "the most serious recent reports (homicide, weapons)"
    plus = f"+{int(extra_min + 0.5)} min"
    if lower_m < 1:
        return f"Lower-exposure stays at least {int(C.AVOID_RADIUS_M)} m from {serious}, which the fastest route passes, for {plus}."
    return (f"Lower-exposure spends {int(lower_m + 0.5)} m within {int(C.AVOID_RADIUS_M)} m of {serious}, "
            f"against {int(fastest_m + 0.5)} m on the fastest route, for {plus}.")


def zone_note(route, fastest) -> str:
    """A sentence for a route that spends less time near the most serious reports than the fastest route."""
    if route.label == "fastest" or round(route.avoid_m) >= round(fastest.avoid_m):
        return ""
    if route.avoid_m < 1:
        return f" Stays {int(C.AVOID_RADIUS_M)} m clear of homicide and weapons reports."
    return f" Spends less time within {int(C.AVOID_RADIUS_M)} m of homicide and weapons reports."


def plan(state, origin: S.LatLon, destination: S.LatLon, radius_m: int, mode: TravelMode = "walk") -> S.RoutesResponse:
    graph = state.graph
    # Walking: closeness to recent reports (walk_pressure). Driving: the allocation model in the exposure bundle.
    bundle = walk_pressure_for(state) if mode == "walk" else state.exposure
    if radius_m not in bundle.radii:
        radius_m = state.settings.DEFAULT_RADIUS_M
    if radius_m not in bundle.radii:
        raise ValueError("default exposure radius is not loaded")

    src, _ = graph.snap(origin.lat, origin.lon, mode)
    dst, _ = graph.snap(destination.lat, destination.lon, mode)
    if src == dst:
        raise NoPathError("same_point")

    blocked = np.asarray(state.hazards.blocked_mask(), dtype=bool)
    # No-go zones around the most serious reports apply to both modes: they are places, not a scoring model.
    avoid = walk_pressure_for(state).avoid_m
    candidates = candidate_set(graph, bundle.mean[radius_m], src, dst, blocked, mode, avoid)
    assessment = assess(candidates, bundle, radius_m)
    lower = candidates.lower_exposure
    if lower is not None and round(lower.avoid_m) < round(candidates.fastest.avoid_m):
        # Keeping clear of homicide and weapons reports is a fact about the route, not a statistical call:
        # recommend it even when the overall report counts can't be told apart.
        assessment.status, assessment.reason = "recommend", None
        assessment.recommended_route_id = lower.route_id
        extra = max(0.0, lower.minutes - candidates.fastest.minutes)
        assessment.message = avoid_message(candidates.fastest.avoid_m, lower.avoid_m, extra)
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
                                         stats.diff_p50, stats.p50, mode)
                        + zone_note(route, candidates.fastest),
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
        mode=mode,
        provenance=build_provenance(state, radius_m, mode),
        origin_snapped=S.LatLon(lat=float(graph.node_lat[src]), lon=float(graph.node_lon[src])),
        destination_snapped=S.LatLon(lat=float(graph.node_lat[dst]), lon=float(graph.node_lon[dst])),
        routes=options,
        decision=decision,
        blocked_edge_count=int(blocked.sum()),
    )
