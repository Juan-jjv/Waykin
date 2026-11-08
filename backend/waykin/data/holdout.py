"""Holdout check (spec A2.8, P2, EPS only): decide on the first 60 days, then count the last 30 days' reports.

Each recommendation is made without seeing the last 30 days. We then compare the reports attributed to the
recommended route and to fastest in those 30 days.
"""
from __future__ import annotations

from datetime import timedelta

import numpy as np

from waykin import constants as C
from waykin.data.allocation import build_allocation
from waykin.data.pipeline import make_bundle, pivot_locations, row_counts
from waykin.data.sources.base import category_config
from waykin.data.stability import assess
from waykin.routing import router
from waykin.routing.types import NoPathError

TRAIN_DAYS = 60
TEST_DAYS = 30


def holdout(graph, source, bbox, categories: list[str], category_preset: str, trips: list[tuple[int, int]],
            radius_m: int = C.DEFAULT_RADIUS_M) -> dict:
    as_of = source.as_of()
    split = as_of - timedelta(days=TEST_DAYS)
    train = pivot_locations(source.window(bbox, categories, split - timedelta(days=TRAIN_DAYS), split))
    test = pivot_locations(source.window(bbox, categories, split, as_of))
    bundle = make_bundle(train, graph, [radius_m], source=source.name, source_label=source.label, as_of=split,
                         category_preset=category_preset, categories=categories, window_days=TRAIN_DAYS)
    A_test, _ = build_allocation(test, graph, radius_m, category_config().severity)
    later = np.asarray(A_test.T @ row_counts(test, A_test))

    recommended_reports, fastest_reports = [], []
    skipped = 0
    for src, dst in trips:
        try:
            cs = router.candidate_set(graph, bundle.mean[radius_m], src, dst, None)
        except NoPathError:
            skipped += 1
            continue
        decision = assess(cs, bundle, radius_m, check_radii=False)
        chosen = next((c for c in cs.alternatives if c.route_id == decision.recommended_route_id), None)
        if chosen is not None:
            recommended_reports.append(float(later[chosen.edge_ids].sum()))
            fastest_reports.append(float(later[cs.fastest.edge_ids].sum()))

    n = len(recommended_reports)
    rec, fast = np.array(recommended_reports), np.array(fastest_reports)
    return {
        "n_trips": len(trips), "n_trips_skipped": skipped, "n_recommend": n, "radius_m": int(radius_m),
        "train_days": TRAIN_DAYS, "test_days": TEST_DAYS,
        "mean_reports_recommended": round(float(rec.mean()), 3) if n else None,
        "mean_reports_fastest": round(float(fast.mean()), 3) if n else None,
        "n_recommended_not_higher": int((rec <= fast).sum()),
        "source": source.name, "graph_hash": graph.graph_hash,
    }
