"""Stability and abstention (spec A2.7). The core of the product: when in doubt, abstain."""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Literal

import numpy as np

from waykin import constants as C

AbstainReason = Literal["thin_data", "indistinguishable", "too_costly", "no_alternative"]

MESSAGES = {
    "thin_data": "Too few reports near these routes to tell them apart.",
    "indistinguishable": "The routes' reported-incident counts overlap too much to call one lower.",
    "too_costly": "Routes with clearly fewer reports add more than 25% to your walk time.",
    "no_alternative": "There is only one reasonable route for this trip.",
}
LABEL_TEXT = {"balanced": "Balanced", "lower_exposure": "Lower-exposure", "fastest": "Fastest", "uncapped": "Uncapped"}


@dataclass
class RouteStats:
    route_id: str
    p10: float
    p50: float
    p90: float
    mean: float
    diff_p10: float | None
    diff_p50: float | None
    diff_p90: float | None
    diff_mean: float | None
    draws_better: int | None


@dataclass
class Assessment:
    status: Literal["recommend", "abstain"]
    recommended_route_id: str | None
    reason: AbstainReason | None
    message: str
    stats: dict[str, RouteStats]
    radius_decisions: dict[int, str] | None
    radius_sensitive: bool | None


def _draws_better(S: np.ndarray) -> np.ndarray:
    """For each route k: draws where route k ≤ (1 - MIN_REDUCTION) · fastest and fastest > 0. Row 0 is fastest."""
    f = S[0]
    return ((f > 0) & (S <= (1.0 - C.MIN_REDUCTION) * f)).sum(axis=1)


def _decide(S: np.ndarray, minutes_per_route: np.ndarray, observed_total: float,
            n_alternatives: int, has_uncapped: bool) -> tuple[str, str | None, int | None, np.ndarray]:
    """Pure decision core on arrays.

    S: (n_routes, N) exposure per draw; row 0 = fastest, rows 1..n_alternatives = alternatives,
    last row = uncapped if has_uncapped. Returns (status, reason, recommended_index, draws_better).
    """
    S = np.asarray(S, dtype=np.float64)
    minutes = np.asarray(minutes_per_route, dtype=np.float64)
    need = math.ceil(C.MIN_DRAW_SHARE * S.shape[1])
    better = _draws_better(S)
    cap = (1.0 + C.MAX_EXTRA_TIME) * minutes[0]

    if n_alternatives == 0 and not has_uncapped:
        return "abstain", "no_alternative", None, better
    if observed_total < C.MIN_REPORTS_FOR_SIGNAL:
        return "abstain", "thin_data", None, better
    qualifying = [k for k in range(1, 1 + n_alternatives) if better[k] >= need and minutes[k] <= cap]
    if qualifying:
        best = min(qualifying, key=lambda k: (minutes[k] - minutes[0], -better[k]))
        return "recommend", None, best, better
    if has_uncapped and better[-1] >= need:
        return "abstain", "too_costly", None, better
    return "abstain", "indistinguishable", None, better


def _routes(cs) -> list:
    return [cs.fastest] + list(cs.alternatives) + ([cs.uncapped] if cs.uncapped is not None else [])


def _route_sums(routes, X) -> np.ndarray:
    """S = R @ X, shape (n_routes, N). Sums only each route's rows: a sparse product would first convert all
    of float32 X to float64, which is several times over the time budget at full size."""
    return np.stack([X[np.asarray(r.edge_ids)].sum(axis=0, dtype=np.float64) for r in routes])


def _assess_one(cs, bundle, radius_m: int):
    routes = _routes(cs)
    S = _route_sums(routes, bundle.X[radius_m])
    union = np.unique(np.concatenate([np.asarray(r.edge_ids) for r in routes]))
    observed_total = float(np.asarray(bundle.observed[radius_m])[union].sum())
    minutes = np.array([r.minutes for r in routes])
    status, reason, idx, better = _decide(S, minutes, observed_total, len(cs.alternatives), cs.uncapped is not None)
    return routes, S, status, reason, idx, better


def _label_of(status, reason, idx, routes) -> str:
    return f"recommend:{routes[idx].label}" if status == "recommend" else f"abstain:{reason}"


def assess(cs, bundle, radius_m: int, *, check_radii: bool = True) -> Assessment:
    routes, S, status, reason, idx, better = _assess_one(cs, bundle, radius_m)
    D = S - S[0]
    stats: dict[str, RouteStats] = {}
    for k, r in enumerate(routes):
        p10, p50, p90 = np.percentile(S[k], [10, 50, 90])
        if k == 0:
            stats[r.route_id] = RouteStats(r.route_id, float(p10), float(p50), float(p90), float(S[k].mean()),
                                           None, None, None, None, None)
        else:
            d10, d50, d90 = np.percentile(D[k], [10, 50, 90])
            stats[r.route_id] = RouteStats(r.route_id, float(p10), float(p50), float(p90), float(S[k].mean()),
                                           float(d10), float(d50), float(d90), float(D[k].mean()), int(better[k]))

    if status == "recommend":
        rec = routes[idx]
        message = (f"{LABEL_TEXT[rec.label]} has at least 15% fewer reported incidents than fastest in "
                   f"{int(better[idx])} of {S.shape[1]} simulations, for +{int(math.floor(rec.minutes - routes[0].minutes + 0.5))} min.")
        rec_id = rec.route_id
    else:
        message, rec_id = MESSAGES[reason], None

    radius_decisions, radius_sensitive = None, None
    if check_radii and len(bundle.radii) > 1:
        radius_decisions = {int(radius_m): _label_of(status, reason, idx, routes)}
        for r in bundle.radii:
            if r != radius_m:
                rr, _, st, rs, ix, _ = _assess_one(cs, bundle, r)
                radius_decisions[int(r)] = _label_of(st, rs, ix, rr)
        radius_sensitive = len(set(radius_decisions.values())) > 1

    return Assessment(status=status, recommended_route_id=rec_id, reason=reason, message=message, stats=stats,
                      radius_decisions=radius_decisions, radius_sensitive=radius_sensitive)
