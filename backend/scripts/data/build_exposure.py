"""Build exposure artifacts: python -m scripts.data.build_exposure --source synthetic|eps [--radii 50,100,200]

Reads the graph (never rebuilds it), loads and validates the source table, pivots it to locations, then for each
radius builds A (with prior nodes), simulates X and saves everything. Prints a summary but never coordinates.
"""
from __future__ import annotations

import argparse
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path

from waykin import constants as C
from waykin.data.pipeline import build_radius, pivot_locations, save_radius
from waykin.data.sources.base import category_config, get_source, validate_source_table
from waykin.routing.graph import load_graph


def build(data_dir: Path, source_name: str, radii: list[int], n_draws: int = C.N_DRAWS) -> dict:
    started = time.time()
    graph_dir = data_dir / "build" / "graph"
    if not (graph_dir / "manifest.json").exists():
        raise FileNotFoundError("graph not built: run python -m scripts.routing.build_graph first")
    graph_manifest = json.loads((graph_dir / "manifest.json").read_text(encoding="utf-8"))
    graph = load_graph(graph_dir)
    bbox = tuple(graph_manifest["bbox"])     # the padded bbox the graph covers

    cfg = category_config()
    source = get_source(source_name, data_dir, graph=graph)
    table = source.load(bbox, cfg.active)
    if table.empty:
        raise ValueError(f"{source.label}: no reports in the graph area for the last {C.WINDOW_DAYS} days")
    validate_source_table(table, bbox)
    locations = pivot_locations(table)
    print(f"{source.label}: {len(locations)} published locations, {int(locations['count'].sum())} reports, "
          f"preset '{cfg.active_preset}'")

    out = data_dir / "build" / "exposure" / source_name
    out.mkdir(parents=True, exist_ok=True)
    (out / "manifest.json").unlink(missing_ok=True)   # a half-finished rebuild must not load as a good one

    allocation = {}
    for r in radii:
        A, X, mean, observed, stats = build_radius(locations, graph, r, n_draws=n_draws)
        save_radius(out, r, A, X, mean, observed)
        allocation[str(r)] = stats
        print(f"  r={r} m: {stats['n_prior']} prior nodes, {stats['nnz']} nonzeros, "
              f"{stats['mean_edges_per_location']} edges/location, fallback {100 * stats['fallback_share']:.1f}%")

    locations.to_parquet(out / "locations.parquet", index=False)
    source.daily(bbox, cfg.active).to_parquet(out / "daily.parquet", index=False)
    last = allocation[str(radii[-1])]
    manifest = {
        "source": source_name, "source_label": source.label, "as_of": source.as_of().isoformat(),
        "window_days": C.WINDOW_DAYS, "radii": sorted(radii), "n_draws": n_draws, "seed": C.SEED,
        "kappa": C.DIRICHLET_KAPPA, "prior_strength": C.PRIOR_STRENGTH,
        "n_published": last["n_published"], "n_prior": last["n_prior"], "graph_hash": graph.graph_hash,
        "category_preset": cfg.active_preset, "categories": cfg.categories, "allocation": allocation,
        "built_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"exposure built in {time.time() - started:.1f} s")
    return manifest


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--source", choices=["synthetic", "eps"], default=os.getenv("EXPOSURE_SOURCE", "synthetic"))
    p.add_argument("--radii", default=",".join(str(r) for r in C.RADII_M))
    p.add_argument("--draws", type=int, default=C.N_DRAWS)
    p.add_argument("--data-dir", default=os.getenv("DATA_DIR", "../data"))
    a = p.parse_args()
    build(Path(a.data_dir), a.source, [int(r) for r in a.radii.split(",")], n_draws=a.draws)


if __name__ == "__main__":
    main()
