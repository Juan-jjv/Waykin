"""The measurement code, with a stand-in for A3's candidate_set and service.plan (still stubs at the time of writing)."""
import json
from datetime import timedelta
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest
import yaml

from scripts.data import _state, abstain_rate, radius_choice
from waykin.data.holdout import holdout
from waykin.data.revalidate import revalidate
from waykin.data.sources.eps import EpsSource
from waykin.data.trips import sample_trips
from waykin.routing import router, service
from waykin.routing.types import NoPathError


def test_trips_are_seeded_and_in_range(grid):
    trips = sample_trips(grid, 30)
    assert trips == sample_trips(grid, 30) and len(trips) == 30
    for a, b in trips:
        assert 800 <= np.hypot(grid.node_x[a] - grid.node_x[b], grid.node_y[a] - grid.node_y[b]) <= 3000


def planner(decisions):
    calls = iter(decisions)

    def plan(state, origin, destination, radius_m):
        d = next(calls)
        if isinstance(d, Exception):
            raise d
        return SimpleNamespace(decision=d)
    return plan


def decision(status, reason=None, by_radius=None):
    return SimpleNamespace(status=status, reason=reason, radius_decisions=by_radius,
                           radius_sensitive=None if by_radius is None else len(set(by_radius.values())) > 1)


def test_abstain_rate_counts_every_outcome_and_records_its_source(grid, monkeypatch):
    rec = {50: "recommend:balanced", 100: "recommend:balanced", 200: "abstain:indistinguishable"}
    ab = {50: "abstain:thin_data", 100: "abstain:thin_data", 200: "abstain:thin_data"}
    monkeypatch.setattr(service, "plan", planner([decision("recommend", by_radius=rec),
                                                  decision("abstain", "thin_data", ab), NoPathError("x")]))
    state = SimpleNamespace(graph=grid, settings=SimpleNamespace(DEFAULT_RADIUS_M=100),
                            exposure=SimpleNamespace(radii=[50, 100, 200], source="synthetic"))
    res = abstain_rate.measure(state, 3)
    assert res["by_status"] == {"recommend": 1, "abstain": 1} and res["by_reason"] == {"thin_data": 1}
    assert res["abstain_share"] == 0.5 and res["errors"] == {"NoPathError": 1}
    assert res["n_radius_sensitive"] == 1 and res["source"] == "synthetic" and res["graph_hash"] == grid.graph_hash
    assert res["agrees_with_majority"] == {"50": 2, "100": 2, "200": 1}
    json.dumps(res)


def test_abstain_rate_does_not_hide_a_programming_error(grid, monkeypatch):
    monkeypatch.setattr(service, "plan", planner([NotImplementedError("stub")]))
    state = SimpleNamespace(graph=grid, settings=SimpleNamespace(DEFAULT_RADIUS_M=100),
                            exposure=SimpleNamespace(radii=[100], source="synthetic"))
    with pytest.raises(NotImplementedError):
        abstain_rate.measure(state, 1)


def test_scripts_refuse_the_stub_planner(monkeypatch):
    monkeypatch.setattr(_state.inspect, "getsource", lambda module: 'route_id="stub-route"')
    with pytest.raises(SystemExit, match="real router"):
        _state.require_real_router()


def test_radius_draft_prefers_the_radius_that_agrees_most_and_labels_synthetic():
    res = {"source": "synthetic", "n_planned": 10, "n_radius_sensitive": 3,
           "by_radius": {"50": {"recommend:balanced": 4, "abstain:thin_data": 6},
                         "100": {"recommend:balanced": 2, "abstain:thin_data": 8},
                         "200": {"abstain:thin_data": 10}},
           "agrees_with_majority": {"50": 9, "100": 8, "200": 7}}
    text = radius_choice.render(res)
    assert "**50 m**" in text and "3 of 10" in text and "says nothing about Edmonton" in text
    assert len(text.strip().splitlines()) <= 11


def test_radius_draft_ties_stay_with_the_default():
    res = {"source": "eps", "n_planned": 1, "n_radius_sensitive": 0, "by_radius": {"50": {}, "100": {}, "200": {}},
           "agrees_with_majority": {"50": 1, "100": 1, "200": 1}}
    assert "**100 m**" in radius_choice.render(res)


def test_revalidate_scores_both_branches(grid, route_sets, route_bundle, monkeypatch):
    monkeypatch.setattr(router, "candidate_set", lambda g, x, src, dst, blocked: route_sets[src])
    res = revalidate(grid, route_bundle, [(0, 9), (1, 9)], n_draws=10)
    assert res["n_recommend"] == 1 and res["n_abstain"] == 1
    assert res["agreement_when_recommend"] == 1.0 and res["flip_rate_when_abstain"] == 0.0
    assert res["source"] == "synthetic" and res["n_draws"] == 10


def test_revalidate_skips_only_trips_with_no_path(grid, route_bundle, monkeypatch):
    def fail(*a):
        raise NoPathError("x")
    monkeypatch.setattr(router, "candidate_set", fail)
    res = revalidate(grid, route_bundle, [(0, 9)], n_draws=5)
    assert res["n_trips_skipped"] == 1 and res["agreement_when_recommend"] is None


def test_holdout_counts_later_reports_on_each_route(grid, route_sets, tmp_path, monkeypatch):
    fastest_node = int(grid.edge_u[route_sets[0].fastest.edge_ids[2]])
    alt_node = int(grid.edge_u[route_sets[0].alternatives[0].edge_ids[2]])
    as_of = pd.Timestamp("2026-09-30").date()

    def rows(node, n, when):
        return [("Theft", grid.node_lat[node], grid.node_lon[node], when)] * n
    # Early: fastest is clearly busier, so the alternative is recommended. Late: reports stay on fastest.
    data = rows(fastest_node, 60, as_of - timedelta(days=60)) + rows(alt_node, 1, as_of - timedelta(days=60)) \
        + rows(fastest_node, 5, as_of)
    raw = tmp_path / "raw" / "eps"
    raw.mkdir(parents=True)
    pd.DataFrame(data, columns=["Kind", "Y", "X", "Reported"]).to_csv(raw / "s.csv", index=False)
    (tmp_path / "m.yaml").write_text(yaml.safe_dump(
        {"columns": {"lat": "Y", "lon": "X", "category": "Kind", "date": "Reported"}, "category_map": {"Theft": "theft"}}),
        encoding="utf-8")
    monkeypatch.setattr(router, "candidate_set", lambda g, x, src, dst, blocked: route_sets[0])

    res = holdout(grid, EpsSource(tmp_path, mapping_path=tmp_path / "m.yaml"), grid.bbox, ["theft"], "all", [(0, 9)])
    assert res["n_recommend"] == 1 and res["source"] == "eps"
    assert res["mean_reports_recommended"] < res["mean_reports_fastest"] and res["n_recommended_not_higher"] == 1
    assert (res["train_days"], res["test_days"]) == (60, 30)
