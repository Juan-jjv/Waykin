"""Offline revalidation (spec A2.8, P1). Long-running: never call it in a request.

`assess` scores a fixed candidate set across the draws. Here, for a sample of draws, we look again per draw:
  * when we recommended a route, is it at least as good as fastest in that draw?
  * when we abstained, rerun the full candidate search with that draw's own exposure, then judge those routes
    with `assess` across all draws, as the app would. How often would that search have led to a recommendation?
    That is the flip rate.

`naive_flip_rate_when_abstain` is the single-draw version: is the draw's own best route clearly lower in that
same draw? It is close to 1 by construction (picking the best of a noisy draw and scoring it on that draw
rewards the noise), so it is reported only to show why the fair version is needed. Never quote it as a result.
"""
from __future__ import annotations

import numpy as np

from waykin import constants as C
from waykin.data.stability import assess
from waykin.routing import router
from waykin.routing.types import NoPathError


def _route_exposure(route, x: np.ndarray) -> float:
    return float(x[route.edge_ids].sum())


def revalidate(graph, bundle, trips: list[tuple[int, int]], n_draws: int = 100, radius_m: int | None = None,
               seed_tag: int = 5) -> dict:
    r = radius_m or bundle.radii[0]
    X = bundle.X[r]
    rng = np.random.default_rng([C.SEED, seed_tag])
    draws = np.sort(rng.choice(X.shape[1], size=min(n_draws, X.shape[1]), replace=False))
    agree = agree_n = flips = naive = flip_n = n_recommend = n_abstain = skipped = 0

    for src, dst in trips:
        try:
            cs = router.candidate_set(graph, bundle.mean[r], src, dst, None)
        except NoPathError:
            skipped += 1
            continue
        decision = assess(cs, bundle, r, check_radii=False)
        fastest = cs.fastest
        cap = (1 + C.MAX_EXTRA_TIME) * fastest.minutes
        recommended = next((c for c in cs.alternatives if c.route_id == decision.recommended_route_id), None)
        n_recommend += recommended is not None
        n_abstain += recommended is None
        for s in draws:
            x = np.asarray(X[:, s], dtype=np.float64)
            base = _route_exposure(fastest, x)
            if recommended is not None:
                agree += _route_exposure(recommended, x) <= base
                agree_n += 1
            else:
                redo = router.candidate_set(graph, x, src, dst, None)
                best = min(_route_exposure(c, x) for c in (redo.fastest, *redo.alternatives) if c.minutes <= cap)
                naive += base > 0 and best <= (1 - C.MIN_REDUCTION) * base
                flips += assess(redo, bundle, r, check_radii=False).status == "recommend"
                flip_n += 1

    return {
        "n_trips": len(trips), "n_trips_skipped": skipped, "n_draws": int(len(draws)), "radius_m": int(r),
        "n_recommend": n_recommend, "n_abstain": n_abstain,
        "agreement_when_recommend": round(agree / agree_n, 4) if agree_n else None,
        "flip_rate_when_abstain": round(flips / flip_n, 4) if flip_n else None,
        "naive_flip_rate_when_abstain": round(naive / flip_n, 4) if flip_n else None,
        "source": bundle.source, "graph_hash": graph.graph_hash,
    }
