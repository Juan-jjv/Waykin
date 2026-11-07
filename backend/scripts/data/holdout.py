"""Holdout (spec A2.8, P2, EPS only): python -m scripts.data.holdout --trips 200

Decides on the first 60 days and counts the last 30. Writes results/data/holdout.json. Needs A3's real router and
an EPS snapshot; there is no synthetic version, because synthetic reports have no dates to split.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from waykin.data.holdout import holdout
from waykin.data.sources.base import category_config
from waykin.data.sources.eps import EpsSource
from waykin.data.trips import sample_trips
from waykin.routing.graph import load_graph


def main() -> None:
    from scripts.data._state import require_real_router, results_dir

    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--trips", type=int, default=200)
    p.add_argument("--data-dir", default=os.getenv("DATA_DIR", "../data"))
    p.add_argument("--results-dir", default=None)
    a = p.parse_args()
    require_real_router()
    data_dir = Path(a.data_dir)
    graph = load_graph(data_dir / "build" / "graph")
    cfg = category_config()
    res = holdout(graph, EpsSource(data_dir), graph.bbox, cfg.active, cfg.active_preset, sample_trips(graph, a.trips))
    out = results_dir(a.results_dir) / "holdout.json"
    out.write_text(json.dumps(res, indent=2), encoding="utf-8")
    print(f"{res['n_recommend']} recommendations; later reports: recommended {res['mean_reports_recommended']}, "
          f"fastest {res['mean_reports_fastest']} -> {out}")


if __name__ == "__main__":
    main()
