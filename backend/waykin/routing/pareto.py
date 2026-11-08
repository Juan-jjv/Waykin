"""Pareto filtering and route option selection."""

from __future__ import annotations

from .types import Candidate, CandidateSet


def _key(route: Candidate) -> tuple[float, float, float]:
    return (route.minutes, route.exposure_mean, round(route.avoid_m, 1))


def nondominated(routes: list[Candidate]) -> list[Candidate]:
    """Routes no other route beats on minutes, exposure and metres inside no-go zones at once."""
    return [
        route for route in routes
        if not any(
            other.route_id != route.route_id
            and all(a <= b for a, b in zip(_key(other), _key(route)))
            and _key(other) != _key(route)
            for other in routes
        )
    ]


def select_options(
    routes: list[Candidate],
    fastest: Candidate,
    max_extra_time: float,
) -> CandidateSet:
    """Two options: fastest, and lower_exposure: within `max_extra_time` of fastest, the route that spends the least
    distance inside no-go zones, then has the least exposure (ties go to the quicker route)."""
    frontier = nondominated(routes)
    if fastest.route_id not in {route.route_id for route in frontier}:
        frontier.insert(0, fastest)
    cap = fastest.minutes * (1.0 + max_extra_time)
    capped = [route for route in frontier if route.minutes <= cap + 1e-9]
    low = min(capped, key=lambda route: (round(route.avoid_m, 1), route.exposure_mean, route.minutes, route.route_id))
    lower: Candidate | None = None
    clearer = round(low.avoid_m, 1) < round(fastest.avoid_m, 1)
    if low.route_id != fastest.route_id and (clearer or low.exposure_mean < fastest.exposure_mean):
        lower = Candidate(**{**vars(low), "label": "lower_exposure"})

    alternatives = [lower] if lower is not None else []
    target = lower.exposure_mean if lower is not None else fastest.exposure_mean
    over_cap = [route for route in frontier if route.minutes > cap and route.exposure_mean < target]
    uncapped_raw = min(over_cap, key=lambda route: (route.exposure_mean, route.minutes, route.route_id), default=None)
    uncapped = Candidate(**{**vars(uncapped_raw), "label": "uncapped"}) if uncapped_raw is not None else None
    fastest_labeled = Candidate(**{**vars(fastest), "label": "fastest"})
    return CandidateSet(fastest_labeled, alternatives, uncapped)
