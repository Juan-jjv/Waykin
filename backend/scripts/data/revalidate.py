"""Offline revalidation (spec A2.8, P1): python -m scripts.data.revalidate --trips 200 --draws 100

Long-running. Writes results/data/revalidation.json. Needs A3's real router.
"""
from __future__ import annotations

import argparse
import json
import time

from waykin.data.revalidate import revalidate
from waykin.data.trips import sample_trips


def main() -> None:
    from scripts.data._state import load_state, require_real_router, results_dir

    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--trips", type=int, default=200)
    p.add_argument("--draws", type=int, default=100)
    p.add_argument("--data-dir", default=None)
    p.add_argument("--results-dir", default=None)
    a = p.parse_args()
    require_real_router()
    started = time.time()
    state = load_state(a.data_dir)
    res = revalidate(state.graph, state.exposure, sample_trips(state.graph, a.trips), n_draws=a.draws)
    res["seconds"] = round(time.time() - started, 1)
    out = results_dir(a.results_dir) / "revalidation.json"
    out.write_text(json.dumps(res, indent=2), encoding="utf-8")
    print(f"agreement when recommending: {res['agreement_when_recommend']}, "
          f"flip rate when abstaining: {res['flip_rate_when_abstain']} ({res['seconds']} s) -> {out}")


if __name__ == "__main__":
    main()
