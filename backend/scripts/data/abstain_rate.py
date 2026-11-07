"""Abstention rate (spec A2.8): python -m scripts.data.abstain_rate --trips 200 [--radii 50,100,200]

Runs A3's service.plan in-process with no hazards on seeded random trips 800-3000 m apart inside the demo area,
and writes results/data/abstention.json. Prints the headline, never coordinates.
"""
from __future__ import annotations

import argparse
import json
from collections import Counter

from waykin import schemas
from waykin.data.trips import sample_trips
from waykin.routing.types import NoPathError, OutsideAreaError


def measure(state, n_trips: int) -> dict:
    from waykin.routing import service

    g, b = state.graph, state.exposure
    trips = sample_trips(g, n_trips)
    radius = state.settings.DEFAULT_RADIUS_M if state.settings.DEFAULT_RADIUS_M in b.radii else b.radii[0]
    by_status, by_reason, errors = Counter(), Counter(), Counter()
    by_radius: dict[str, Counter] = {}
    agrees_with_majority: Counter = Counter()
    n_sensitive = 0
    for src, dst in trips:
        origin = schemas.LatLon(lat=float(g.node_lat[src]), lon=float(g.node_lon[src]))
        destination = schemas.LatLon(lat=float(g.node_lat[dst]), lon=float(g.node_lon[dst]))
        try:
            decision = service.plan(state, origin, destination, radius).decision
        except (OutsideAreaError, NoPathError) as ex:
            errors[type(ex).__name__] += 1
            continue
        by_status[decision.status] += 1
        if decision.reason:
            by_reason[decision.reason] += 1
        n_sensitive += bool(decision.radius_sensitive)
        outcomes = {str(r): o for r, o in (decision.radius_decisions or {}).items()}
        for r, outcome in outcomes.items():
            by_radius.setdefault(r, Counter())[outcome] += 1
        if outcomes:
            majority = Counter(outcomes.values()).most_common(1)[0][0]
            agrees_with_majority.update(r for r, o in outcomes.items() if o == majority)
    n_planned = sum(by_status.values())
    return {
        "n_trips": len(trips), "n_planned": n_planned, "radius_m": radius,
        "by_status": dict(by_status), "by_reason": dict(by_reason),
        "abstain_share": round(by_status.get("abstain", 0) / n_planned, 4) if n_planned else None,
        "by_radius": {r: dict(c) for r, c in by_radius.items()} or None,
        "n_radius_sensitive": n_sensitive if by_radius else None,
        "agrees_with_majority": dict(agrees_with_majority) or None,
        "errors": dict(errors), "source": b.source, "graph_hash": g.graph_hash,
    }


def main() -> None:
    from scripts.data._state import load_state, require_real_router, results_dir

    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--trips", type=int, default=200)
    p.add_argument("--radii", default=None, help="radii to load, e.g. 50,100,200 (default: LOAD_RADII)")
    p.add_argument("--data-dir", default=None)
    p.add_argument("--results-dir", default=None)
    a = p.parse_args()
    require_real_router()
    res = measure(load_state(a.data_dir, a.radii), a.trips)
    out = results_dir(a.results_dir) / "abstention.json"
    out.write_text(json.dumps(res, indent=2), encoding="utf-8")
    if res["abstain_share"] is None:
        print(f"no trips planned -> {out}")
        return
    print(f"{res['n_planned']} of {res['n_trips']} trips planned on {res['source']} data; "
          f"abstained on {res['by_status'].get('abstain', 0)} -> {out}")
    if res["abstain_share"] > 0.6:
        print("Note: above 60% is expected. The pitch frames it as 'the honest answer is often: it doesn't matter'.")


if __name__ == "__main__":
    main()
