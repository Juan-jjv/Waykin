"""Build the precomputed OSM walking graph used by WayKin."""

from __future__ import annotations

import argparse
import time

from waykin.routing.build import DEMO_BBOX, build_osm_graph, save_graph


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bbox", nargs=4, type=float, metavar=("WEST", "SOUTH", "EAST", "NORTH"), default=DEMO_BBOX)
    parser.add_argument("--output", default="data/build/graph", help="graph artifact directory")
    parser.add_argument("--cache", default="data/build/graph/osm_cache", help="OSMnx cache directory")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    started = time.perf_counter()
    graph = build_osm_graph(tuple(args.bbox), cache_dir=args.cache)
    manifest = save_graph(graph, args.output)
    elapsed = time.perf_counter() - started
    print(f"Built graph: {graph.n_nodes:,} nodes, {graph.n_edges:,} edges in {elapsed:.1f}s")
    print(f"Artifacts: {args.output} (sha256 {manifest['graph_hash']})")


if __name__ == "__main__":
    main()
