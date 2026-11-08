"""Build the demo-area walking graph: python -m scripts.routing.build_graph [--bbox w,s,e,n] [--osm-file F] [--out DIR]

Without --osm-file the streets are downloaded from Overpass. With it they are read from an OpenStreetMap extract,
e.g. Geofabrik's alberta-latest.osm.pbf, which avoids the shared Overpass servers for city-sized areas.
"""
import argparse
import os
from pathlib import Path

from waykin import constants as C
from waykin.routing.build import build


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--bbox", help="west,south,east,north (defaults to DEMO_BBOX)")
    p.add_argument("--osm-file", help="read streets from this .osm.pbf extract instead of Overpass")
    p.add_argument("--out", default=str(Path(os.getenv("DATA_DIR", "../data")) / "build" / "graph"))
    a = p.parse_args()
    bbox = tuple(float(x) for x in a.bbox.split(",")) if a.bbox else C.DEMO_BBOX
    stats = build(Path(a.out), bbox, osm_file=Path(a.osm_file) if a.osm_file else None)
    print(f"graph built: {stats['n_nodes']} nodes, {stats['n_edges']} edges, "
          f"hash {stats['graph_hash']}, {stats['seconds']} s -> {a.out}")


if __name__ == "__main__":
    main()
