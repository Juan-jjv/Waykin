"""Regenerate the mock-mode fixtures: python -m waykin.mocks.make_fixtures

Routes follow the streets of the 12×12 test grid (inside DEMO_BBOX near the U of A). Every number in
these files is a MOCK value for UI development, not a measurement.
"""
from __future__ import annotations

import json
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import numpy as np

from waykin import constants as C
from waykin import schemas as S
from waykin.routing.explain import explanation_text, whole_minutes
from waykin.routing.testing import make_grid_graph
from waykin.routing.types import route_id_for

OUT = Path(__file__).parent
N = 12
G = make_grid_graph()
EDGE = {(int(u), int(v)): e for e, (u, v) in enumerate(zip(G.edge_u, G.edge_v))}


def node(r, c):
    return r * N + c


def walk(*corners):
    """Node path through grid corners (row, col), moving along one axis at a time."""
    path = [node(*corners[0])]
    for (r0, c0), (r1, c1) in zip(corners, corners[1:]):
        r, c = r0, c0
        while (r, c) != (r1, c1):
            if c != c1:
                c += 1 if c1 > c else -1
            else:
                r += 1 if r1 > r else -1
            path.append(node(r, c))
    return path


def edges_of(path):
    return [EDGE[(min(a, b), max(a, b))] for a, b in zip(path, path[1:])]


def geom(path):
    return [[round(float(G.node_lat[n]), 6), round(float(G.node_lon[n]), 6)] for n in path]


def iv(p10, p50, p90):
    return S.Interval(p10=p10, p50=p50, p90=p90, mean=round((p10 + p50 + p90) / 3, 2))


def option(label, path, fastest_min, exp, diff, better, top_idx, expl=None):
    e = edges_of(path)
    minutes = round(len(e) * 100 / C.WALK_SPEED_M_PER_MIN, 1)
    top = [S.TopSegment(edge_id=e[i], name=G.edge_name[e[i]], attributed=round(exp.p50 * 0.2, 1),
                        geometry=geom(path[i:i + 2])) for i in top_idx]
    return S.RouteOption(route_id=route_id_for(np.array(e)), label=label, minutes=minutes,
                         extra_minutes=round(minutes - fastest_min, 1), distance_m=len(e) * 100.0, exposure=exp,
                         exposure_diff_vs_fastest=diff, draws_better=better, geometry=geom(path), edge_ids=e,
                         top_segments=top, explanation=explanation_text(label, minutes, minutes - fastest_min,
                                                                         diff.p50 if diff else None, exp.p50))


def provenance(radius=100):
    return S.Provenance(source="synthetic", source_label="Synthetic data (mock mode)", as_of=date(2026, 10, 31),
                        window_days=C.WINDOW_DAYS, radius_m=radius, units=C.UNITS, disclaimer=C.DISCLAIMER)


THRESH = S.Thresholds(min_reduction=C.MIN_REDUCTION, min_draw_share=C.MIN_DRAW_SHARE, max_extra_time=C.MAX_EXTRA_TIME)


def ll(n):
    return S.LatLon(lat=round(float(G.node_lat[n]), 6), lon=round(float(G.node_lon[n]), 6))


def main():
    # ---- recommend: (0,0) -> (8,10)
    f_path = walk((0, 0), (0, 10), (8, 10))
    b_path = walk((0, 0), (0, 5), (9, 5), (9, 10), (8, 10))
    l_path = walk((0, 0), (10, 0), (10, 10), (8, 10))
    fmin = round(len(f_path[1:]) * 100 / C.WALK_SPEED_M_PER_MIN, 1)
    fastest = option("fastest", f_path, fmin, iv(9.8, 12.4, 15.1), None, None, [9, 12, 3],
                     "Fastest option, 22 min. About 12.4 reported incidents.")
    balanced = option("balanced", b_path, fmin, iv(4.9, 6.6, 8.5), iv(-7.9, -5.8, -3.6), 471, [2, 7],
                      "+2 min vs fastest. About 5.8 fewer reported incidents attributed to segments along this route (90 days).")
    lower = option("lower_exposure", l_path, fmin, iv(3.1, 4.4, 6.0), iv(-10.2, -8.0, -5.9), 492, [14],
                   "+5 min vs fastest. About 8.0 fewer reported incidents attributed to segments along this route (90 days).")
    rec = S.RoutesResponse(
        provenance=provenance(), origin_snapped=ll(f_path[0]), destination_snapped=ll(f_path[-1]),
        routes=[fastest, balanced, lower],
        decision=S.Decision(status="recommend", recommended_route_id=balanced.route_id, reason=None,
                            message=f"Balanced has at least 15% fewer reported incidents than fastest in 471 of "
                                    f"{C.N_DRAWS} simulations, for +{whole_minutes(balanced.extra_minutes)} min.",
                            radius_sensitive=None, radius_decisions=None, thresholds=THRESH, n_draws=C.N_DRAWS),
        blocked_edge_count=0)

    # ---- abstain (indistinguishable): (2,2) -> (9,7)
    fa = walk((2, 2), (2, 7), (9, 7))
    ba = walk((2, 2), (9, 2), (9, 7))
    famin = round(len(fa[1:]) * 100 / C.WALK_SPEED_M_PER_MIN, 1)
    abst = S.RoutesResponse(
        provenance=provenance(), origin_snapped=ll(fa[0]), destination_snapped=ll(fa[-1]),
        routes=[option("fastest", fa, famin, iv(5.2, 7.0, 9.1), None, None, [6, 1],
                       "Fastest option, 15 min. About 7.0 reported incidents."),
                option("balanced", ba, famin, iv(4.6, 6.5, 8.8), iv(-2.4, -0.5, 1.6), 212, [3],
                       "+0 min vs fastest. About the same number of reported incidents.")],
        decision=S.Decision(status="abstain", recommended_route_id=None, reason="indistinguishable",
                            message="The routes' reported-incident counts overlap too much to call one lower.",
                            radius_sensitive=None, radius_decisions=None, thresholds=THRESH, n_draws=C.N_DRAWS),
        blocked_edge_count=0)

    # ---- hazard: on the recommended (balanced) route at row 9 between cols 6 and 7,
    #      plus the abstain fastest route at row 2 between cols 4 and 5.
    hz_edges = sorted({EDGE[(node(9, 6), node(9, 7))], EDGE[(node(2, 4), node(2, 5))]})
    mid_lat = float((G.node_lat[node(9, 6)] + G.node_lat[node(9, 7)]) / 2)
    mid_lon = float((G.node_lon[node(9, 6)] + G.node_lon[node(9, 7)]) / 2)
    t = datetime(2026, 11, 7, 12, 0, tzinfo=timezone.utc)
    hazard = S.Hazard(hazard_id="mock-closure", kind="closure", lat=round(mid_lat, 6), lon=round(mid_lon, 6),
                      radius_m=30, description="Road closure (mock)", source="demo", created_at=t,
                      expires_at=t + timedelta(days=365), edge_ids=hz_edges)
    assert set(hz_edges) & set(balanced.edge_ids) and set(hz_edges) & set(abst.routes[0].edge_ids)

    # ---- reroute: from (9,5) to (8,10) avoiding row 9 between cols 6-7
    rr_path = walk((9, 5), (8, 5), (8, 10))
    rr_min = round(len(rr_path[1:]) * 100 / C.WALK_SPEED_M_PER_MIN, 1)
    reroute = S.RoutesResponse(
        provenance=provenance(), origin_snapped=ll(rr_path[0]), destination_snapped=ll(rr_path[-1]),
        routes=[option("fastest", rr_path, rr_min, iv(1.9, 2.8, 3.9), None, None, [2],
                       "Fastest option, 8 min. About 2.8 reported incidents.")],
        decision=S.Decision(status="abstain", recommended_route_id=None, reason="no_alternative",
                            message="There is only one reasonable route for this trip.", radius_sensitive=None,
                            radius_decisions=None, thresholds=THRESH, n_draws=C.N_DRAWS),
        blocked_edge_count=len(hz_edges))
    assert not set(hz_edges) & set(reroute.routes[0].edge_ids)

    # ---- incidents: a few intersection points along the routes
    rng = np.random.default_rng(C.SEED)
    pts = []
    for n in sorted(set(f_path[::2] + fa[::3] + [node(r, c) for r in (3, 6) for c in (3, 8)])):
        cnt = int(rng.integers(1, 7))
        pts.append(S.IncidentPoint(location_id=f"mock-{n}", lat=round(float(G.node_lat[n]), 6),
                                   lon=round(float(G.node_lon[n]), 6), count=cnt,
                                   by_category={"theft": cnt - cnt // 3, "assault": cnt // 3} if cnt // 3 else {"theft": cnt}))
    incidents = S.IncidentsResponse(provenance=provenance(), points=pts)

    meta = S.Meta(provenance=provenance(), radii=[100], default_radius_m=100, bbox=list(C.DEMO_BBOX),
                  categories=["assault", "robbery", "break_and_enter", "theft_from_vehicle", "theft"],
                  category_preset="all", relay_mode="e2ee", n_draws=C.N_DRAWS, thresholds=THRESH,
                  demo_mode=False, demo_presets=[
                      S.DemoPreset(id="mock-recommend", name="Campus to Whyte (mock)", description="Recommends a detour",
                                   origin=ll(f_path[0]), destination=ll(f_path[-1]), expected="recommend"),
                      S.DemoPreset(id="mock-abstain", name="Short hop (mock)", description="Routes are about the same",
                                   origin=ll(fa[0]), destination=ll(fa[-1]), expected="abstain"),
                      # /api/demo/trigger/mock-reroute adds hazard_closure (demo/__init__.py), which blocks
                      # the abstain fixture's fastest route; routes_reroute avoids it.
                      S.DemoPreset(id="mock-reroute", name="Closure on the way (mock)",
                                   description="A scripted closure lands on the route; the walker reroutes",
                                   origin=ll(fa[0]), destination=ll(fa[-1]), expected="reroute")])

    for name, model in [("meta", meta), ("incidents", incidents), ("routes_recommend", rec),
                        ("routes_abstain", abst), ("routes_reroute", reroute), ("hazard_closure", hazard)]:
        (OUT / f"{name}.json").write_text(json.dumps(model.model_dump(mode="json"), indent=1) + "\n")
    print("fixtures written to", OUT)


if __name__ == "__main__":
    main()
