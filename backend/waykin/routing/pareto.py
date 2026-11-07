"""Deterministic Pareto filtering and route-option selection."""

from __future__ import annotations

from collections.abc import Iterable

from .types import RouteCandidate, RouteSet


def nondominated(routes: Iterable[RouteCandidate]) -> list[RouteCandidate]:
    """Return routes not dominated on (minutes, exposure), preserving order."""
    items = list(routes)
    kept: list[RouteCandidate] = []
    for candidate in items:
        dominated = any(
            other.route_id != candidate.route_id
            and other.minutes <= candidate.minutes
            and other.exposure_mean <= candidate.exposure_mean
            and (other.minutes < candidate.minutes or other.exposure_mean < candidate.exposure_mean)
            for other in items
        )
        if not dominated:
            kept.append(candidate)
    return kept


def select_options(
    routes: Iterable[RouteCandidate],
    fastest: RouteCandidate,
    max_extra_time: float = 0.25,
    balanced_min_reduction: float = 0.15,
) -> RouteSet:
    """Choose the capped low-exposure route, knee route, and over-cap route."""
    frontier = nondominated(routes)
    if not any(route.route_id == fastest.route_id for route in frontier):
        # A λ=0 shortest path cannot ordinarily be dominated, but retaining it
        # makes ties in exposure deterministic and keeps the contract explicit.
        frontier.insert(0, fastest)

    cap = fastest.minutes * (1.0 + max_extra_time)
    capped = [route for route in frontier if route.minutes <= cap + 1e-9]
    lower = min(capped, key=lambda route: (route.exposure_mean, route.minutes, route.route_id))
    if lower.route_id == fastest.route_id or lower.exposure_mean >= fastest.exposure_mean - 1e-12:
        lower = None

    balanced = None
    if lower is not None and fastest.exposure_mean - lower.exposure_mean >= balanced_min_reduction:
        dx = lower.minutes - fastest.minutes
        dy = lower.exposure_mean - fastest.exposure_mean
        span_minutes = dx if abs(dx) > 1e-12 else 1.0
        span_exposure = dy if abs(dy) > 1e-12 else 1.0
        interior = [
            route for route in capped
            if route.route_id not in {fastest.route_id, lower.route_id}
        ]
        if interior:
            def chord_distance(route: RouteCandidate) -> tuple[float, float, str]:
                x = (route.minutes - fastest.minutes) / span_minutes
                y = (route.exposure_mean - fastest.exposure_mean) / span_exposure
                # Distance from the normalized endpoint chord y=x.
                return (abs(y - x), -route.minutes, route.route_id)

            best = max(interior, key=chord_distance)
            if best.exposure_mean <= fastest.exposure_mean - balanced_min_reduction:
                balanced = best

    target_exposure = lower.exposure_mean if lower is not None else fastest.exposure_mean
    over_cap = [route for route in frontier if route.minutes > cap and route.exposure_mean < target_exposure]
    uncapped = min(over_cap, key=lambda route: (route.exposure_mean, route.minutes, route.route_id), default=None)
    return RouteSet(fastest, lower, balanced, uncapped, tuple(frontier))
