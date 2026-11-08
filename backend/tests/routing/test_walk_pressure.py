"""Walking incident pressure: closeness to recent reports, not a share of them. Locations below are made up."""
import json
from datetime import date, timedelta

import numpy as np
import pandas as pd
import pytest

from waykin import constants as C

from waykin.data.sources.base import category_config
from waykin.data.stability import assess
from waykin.data.walk_pressure import build_walk_pressure, location_weights
from waykin.routing.router import candidate_set
from waykin.routing.testing import make_grid_graph

AS_OF = date(2026, 11, 6)


def _reports(graph, spots):
    """spots: [(lat, lon, n_reports, days_old, category)] -> (locations, daily)."""
    locs, daily = [], []
    for i, (lat, lon, n, age, cat) in enumerate(spots):
        lid = f"L{i:03d}"
        locs.append((lid, lat, lon, n, json.dumps({cat: n})))
        daily.append((lid, AS_OF - timedelta(days=age), cat, n))
    return (pd.DataFrame(locs, columns=["location_id", "lat", "lon", "count", "counts_by_category"]),
            pd.DataFrame(daily, columns=["location_id", "date", "category", "count"]))


def _mid(g, a, b):
    return (float(g.node_lat[a] + g.node_lat[b]) / 2, float(g.node_lon[a] + g.node_lon[b]) / 2)


def _edge(g, a, b):
    return int(np.flatnonzero(((g.edge_u == a) & (g.edge_v == b)) | ((g.edge_u == b) & (g.edge_v == a)))[0])


def test_pressure_is_local_and_walking_past_counts_a_report_about_once():
    g = make_grid_graph(12, spacing_m=100.0)
    lat, lon = _mid(g, 5 * 12 + 5, 5 * 12 + 6)                 # on Test Ave 6, mid-block
    locs, daily = _reports(g, [(lat, lon, 1, 0, "theft")])           # severity 1 (least serious), today: weight 1
    wp = build_walk_pressure(g, locs, daily, AS_OF, [100])
    field = wp.mean[100]
    row = [_edge(g, 5 * 12 + c, 5 * 12 + c + 1) for c in range(11)]
    assert field[row].sum() == pytest.approx(1.0, rel=0.03)      # straight past it: about its weight, once
    far = [_edge(g, c, c + 1) for c in range(11)]                # Test Ave 1, 500 m away
    assert field[far].sum() == 0.0


def test_recency_and_severity_weights():
    g = make_grid_graph(4)
    lat, lon = _mid(g, 0, 1)
    locs, daily = _reports(g, [(lat, lon, 2, 14, "assault"), (lat, lon, 4, 40, "theft")])
    w = location_weights(locs, daily, AS_OF)
    assert list(w["n"]) == [2]                                     # the 40-day-old reports are outside the window
    sev = category_config().severity
    assert w["weight"].iloc[0] == pytest.approx(2 * 0.5 * sev["assault"])   # one half-life old


def test_walking_route_avoids_a_hotspot_on_the_direct_line():
    g = make_grid_graph(12, spacing_m=100.0, drive_kmh=40.0)
    zero = np.zeros(g.n_edges)
    src, dst = 5 * 12, 5 * 12 + 11                                 # straight along Test Ave 6
    direct = candidate_set(g, zero, src, dst, mode="walk").fastest
    spots = [(*_mid(g, 5 * 12 + c, 5 * 12 + c + 1), 6, 1, "assault") for c in (4, 5, 6)]
    locs, daily = _reports(g, spots)
    wp = build_walk_pressure(g, locs, daily, AS_OF, [100])
    cs = candidate_set(g, wp.mean[100], src, dst, mode="walk")
    lower = cs.lower_exposure
    assert lower is not None and lower.minutes <= direct.minutes * (1 + C.MAX_EXTRA_TIME)
    assert wp.mean[100][lower.edge_ids].sum() < 0.2 * wp.mean[100][direct.edge_ids].sum()
    result = assess(cs, wp, 100, check_radii=False)
    assert result.status == "recommend"                           # 18 recent reports: the detour clearly holds
    rec = next(r for r in cs.alternatives if r.route_id == result.recommended_route_id)
    lowest = min(r.exposure_mean for r in cs.alternatives)
    drop = cs.fastest.exposure_mean - lowest
    assert rec.exposure_mean <= lowest + 0.1 * drop + 1e-9          # walking: (near) the fewest reports wins


def test_one_old_minor_report_is_too_uncertain_to_recommend():
    g = make_grid_graph(12, spacing_m=100.0)
    src, dst = 5 * 12, 5 * 12 + 11
    locs, daily = _reports(g, [(*_mid(g, 5 * 12 + 5, 5 * 12 + 6), 1, 25, "mischief")])
    wp = build_walk_pressure(g, locs, daily, AS_OF, [100])
    cs = candidate_set(g, wp.mean[100], src, dst, mode="walk")
    assert assess(cs, wp, 100, check_radii=False).status == "abstain"


def test_cars_only_edges_neither_take_nor_dilute_walking_pressure():
    g = make_grid_graph(6, drive_kmh=40.0)
    lat, lon = _mid(g, 2 * 6 + 2, 2 * 6 + 3)
    locs, daily = _reports(g, [(lat, lon, 3, 0, "robbery")])
    before = build_walk_pressure(g, locs, daily, AS_OF, [100]).mean[100]
    neighbour = _edge(g, 2 * 6 + 2, 3 * 6 + 2)
    g.edge_walk[neighbour] = False                                 # make a nearby street cars-only
    after = build_walk_pressure(g, locs, daily, AS_OF, [100]).mean[100]
    assert after[neighbour] == 0.0
    others = np.arange(g.n_edges) != neighbour
    np.testing.assert_allclose(after[others], before[others])      # nothing is redistributed


def test_no_reports_gives_zero_field_and_thin_data():
    g = make_grid_graph(6)
    locs, daily = _reports(g, [])
    wp = build_walk_pressure(g, locs, daily, AS_OF, [100])
    assert wp.mean[100].sum() == 0.0
    cs = candidate_set(g, wp.mean[100], 0, 35, mode="walk")
    a = assess(cs, wp, 100, check_radii=False)
    assert a.status == "abstain" and a.reason in ("no_alternative", "thin_data")


def test_severity_scale_runs_from_light_to_dark():
    sev = category_config().severity
    assert min(sev.values()) == 1.0 and max(sev.values()) == 5.0
    assert sev["homicide"] == 5.0 and sev["indecent_act"] < sev["assault"] < sev["weapons"] < sev["homicide"]
    assert all(c in sev for c in category_config().categories)


def test_a_homicide_outweighs_several_thefts():
    g = make_grid_graph(4)
    lat, lon = _mid(g, 0, 1)
    locs, daily = _reports(g, [(lat, lon, 1, 0, "homicide"), (lat + 0.002, lon, 4, 0, "theft")])
    w = location_weights(locs, daily, AS_OF).set_index("location_id")["weight"]
    assert w["L000"] > w["L001"]


# ---- no-go zones around the most serious reports (homicide, weapons)

def _straight_trip(g):
    return 5 * 12, 5 * 12 + 11                                    # along Test Ave 6, 1.1 km


def test_zones_cover_only_streets_near_serious_reports():
    g = make_grid_graph(12, spacing_m=100.0)
    weapons = _mid(g, 5 * 12 + 5, 5 * 12 + 6)
    theft = _mid(g, 1 * 12 + 2, 1 * 12 + 3)
    locs, daily = _reports(g, [(*weapons, 1, 20, "weapons"), (*theft, 9, 0, "theft")])
    wp = build_walk_pressure(g, locs, daily, AS_OF, [100])
    assert wp.n_avoid == 1
    hit = _edge(g, 5 * 12 + 5, 5 * 12 + 6)
    assert wp.avoid_m[hit] == pytest.approx(100.0)                 # the whole block runs through the circle
    assert wp.avoid_m[_edge(g, 1 * 12 + 2, 1 * 12 + 3)] == 0.0     # many thefts, but no zone
    assert wp.avoid_m[_edge(g, 9 * 12 + 5, 9 * 12 + 6)] == 0.0     # 400 m away


def test_lower_route_keeps_clear_of_a_zone_when_the_cap_allows():
    g = make_grid_graph(12, spacing_m=100.0)
    src, dst = _straight_trip(g)
    locs, daily = _reports(g, [(*_mid(g, 5 * 12 + 5, 5 * 12 + 6), 1, 25, "homicide")])
    wp = build_walk_pressure(g, locs, daily, AS_OF, [100])
    cs = candidate_set(g, wp.mean[100], src, dst, mode="walk", avoid=wp.avoid_m)
    assert cs.fastest.avoid_m > 0
    low = cs.lower_exposure
    assert low is not None and low.avoid_m == 0.0
    assert low.minutes <= cs.fastest.minutes * (1 + C.MAX_EXTRA_TIME)


def test_zones_never_push_the_lower_route_past_the_time_cap():
    g = make_grid_graph(12, spacing_m=100.0)
    src, dst = 5 * 12 + 4, 5 * 12 + 7                              # 300 m: going round costs more than 40%
    locs, daily = _reports(g, [(*_mid(g, 5 * 12 + 5, 5 * 12 + 6), 2, 3, "weapons")])
    wp = build_walk_pressure(g, locs, daily, AS_OF, [100])
    cs = candidate_set(g, wp.mean[100], src, dst, mode="walk", avoid=wp.avoid_m)
    assert cs.lower_exposure is None or cs.lower_exposure.minutes <= cs.fastest.minutes * (1 + C.MAX_EXTRA_TIME) + 1e-9


def test_plan_recommends_the_zone_free_route():
    from types import SimpleNamespace

    from waykin import schemas as S
    from waykin.config import Settings
    from waykin.data.bundle import make_synthetic_bundle_for_tests
    from waykin.routing.service import plan

    g = make_grid_graph(12, spacing_m=100.0)
    src, dst = _straight_trip(g)
    locs, daily = _reports(g, [(*_mid(g, 5 * 12 + 5, 5 * 12 + 6), 1, 25, "homicide")])
    state = SimpleNamespace(graph=g, exposure=make_synthetic_bundle_for_tests(g), settings=Settings(),
                            walk=build_walk_pressure(g, locs, daily, AS_OF, [100]),
                            hazards=SimpleNamespace(blocked_mask=lambda: np.zeros(g.n_edges, bool)))
    point = lambda n: S.LatLon(lat=float(g.node_lat[n]), lon=float(g.node_lon[n]))  # noqa: E731
    r = plan(state, point(src), point(dst), 100, "walk")
    low = next(x for x in r.routes if x.label == "lower_exposure")
    assert r.decision.status == "recommend" and r.decision.recommended_route_id == low.route_id
    assert "homicide, weapons" in r.decision.message and "clear of homicide and weapons" in low.explanation
