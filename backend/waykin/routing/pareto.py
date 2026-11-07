"""Pareto filtering and route option selection."""

from __future__ import annotations

from .types import Candidate, CandidateSet


def nondominated(routes: list[Candidate]) -> list[Candidate]:
    return [
        route for route in routes
        if not any(
            other.route_id != route.route_id
            and other.minutes <= route.minutes
            and other.exposure_mean <= route.exposure_mean
            and (other.minutes < route.minutes or other.exposure_mean < route.exposure_mean)
            for other in routes
        )
    ]


def select_options(
    routes: list[Candidate],
    fastest: Candidate,
    max_extra_time: float,
    balanced_min_reduction: float,
) -> CandidateSet:
    frontier = nondominated(routes)
    if fastest.route_id not in {route.route_id for route in frontier}:
        frontier.insert(0, fastest)
    cap = fastest.minutes * (1.0 + max_extra_time)
    capped = [route for route in frontier if route.minutes <= cap + 1e-9]
    low = min(capped, key=lambda route: (route.exposure_mean, route.minutes, route.route_id))
    lower: Candidate | None = None
    if low.route_id != fastest.route_id and low.exposure_mean < fastest.exposure_mean:
        lower = Candidate(**{**vars(low), "label": "lower_exposure"})

    balanced: Candidate | None = None
    if lower is not None and fastest.exposure_mean - lower.exposure_mean >= balanced_min_reduction:
        dx = lower.minutes - fastest.minutes or 1.0
        dy = lower.exposure_mean - fastest.exposure_mean or 1.0
        interior = [route for route in capped if route.route_id not in {fastest.route_id, lower.route_id}]
        if interior:
            best = max(
                interior,
                key=lambda route: (
                    abs((route.exposure_mean - fastest.exposure_mean) / dy
                        - (route.minutes - fastest.minutes) / dx),
                    -route.minutes,
                    route.route_id,
                ),
            )
            if best.exposure_mean <= fastest.exposure_mean - balanced_min_reduction:
                balanced = Candidate(**{**vars(best), "label": "balanced"})

    alternatives = ([lower] if lower is not None else []) + ([balanced] if balanced is not None else [])
    target = lower.exposure_mean if lower is not None else fastest.exposure_mean
    over_cap = [route for route in frontier if route.minutes > cap and route.exposure_mean < target]
    uncapped_raw = min(over_cap, key=lambda route: (route.exposure_mean, route.minutes, route.route_id), default=None)
    uncapped = Candidate(**{**vars(uncapped_raw), "label": "uncapped"}) if uncapped_raw is not None else None
    fastest_labeled = Candidate(**{**vars(fastest), "label": "fastest"})
    return CandidateSet(fastest_labeled, alternatives, uncapped)
