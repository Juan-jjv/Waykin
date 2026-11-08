"""Offline graph build from OpenStreetMap (needs the `build` extra, and network access unless given an extract).

Run it through `python -m scripts.routing.build_graph`. Never imported by the server.
"""
from __future__ import annotations

import math
import os
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from xml.sax.saxutils import quoteattr

import numpy as np
import shapely
from shapely.geometry import LineString

from waykin import constants as C
from waykin.routing.graph import assemble_graph, utm_to_latlon, write_artifacts


def padded_bbox(bbox=C.DEMO_BBOX, pad_m: float = C.GRAPH_PAD_M) -> tuple[float, float, float, float]:
    w, s, e, n = bbox
    dlat = pad_m / 111_320.0
    dlon = pad_m / (111_320.0 * math.cos(math.radians((s + n) / 2)))
    return (w - dlon, s - dlat, e + dlon, n + dlat)


def _download(ox, bbox):
    w, s, e, n = bbox
    major = int(ox.__version__.split(".")[0])
    if major >= 2:
        return ox.graph_from_bbox(bbox=(w, s, e, n), network_type="walk", simplify=True)
    return ox.graph_from_bbox(n, s, e, w, network_type="walk", simplify=True)  # osmnx 1.x signature


# osmnx's "walk" network filter, applied to an OpenStreetMap extract instead of an Overpass query.
_WALK_EXCLUDE = {
    "highway": re.compile("abandoned|bus_guideway|construction|cycleway|motor|no|planned|platform|proposed|raceway|"
                          "razed|rest_area|services"),
    "area": re.compile("yes"), "access": re.compile("private"), "foot": re.compile("no"),
    "service": re.compile("private"), "sidewalk": re.compile("separate"), "sidewalk:both": re.compile("separate"),
    "sidewalk:left": re.compile("separate"), "sidewalk:right": re.compile("separate"),
}


def is_walkable(tags: dict[str, str]) -> bool:
    if "highway" not in tags:
        return False
    return not any(key in tags and pattern.search(tags[key]) for key, pattern in _WALK_EXCLUDE.items())


def extract_walk_ways(osm_file: Path, bbox, xml_out: Path) -> int:
    """Write the walkable ways touching `bbox` (with all their nodes) from a .osm.pbf extract as OSM XML."""
    import osmium

    w, s, e, n = bbox
    nodes: dict[int, tuple[float, float]] = {}
    ways: list[tuple[int, list[int], dict[str, str]]] = []
    processor = (osmium.FileProcessor(str(osm_file)).with_locations()
                 .with_filter(osmium.filter.EntityFilter(osmium.osm.WAY)))
    for way in processor:
        tags = {t.k: t.v for t in way.tags}
        if not is_walkable(tags):
            continue
        refs = [(nd.ref, nd.location) for nd in way.nodes if nd.location.valid()]
        if len(refs) < 2 or not any(w <= loc.lon <= e and s <= loc.lat <= n for _, loc in refs):
            continue
        for ref, loc in refs:
            nodes[ref] = (loc.lat, loc.lon)
        ways.append((way.id, [ref for ref, _ in refs], tags))

    with open(xml_out, "w", encoding="utf-8") as f:
        f.write('<?xml version="1.0" encoding="UTF-8"?>\n<osm version="0.6">\n')
        for ref, (lat, lon) in nodes.items():
            f.write(f'<node id="{ref}" lat="{lat:.7f}" lon="{lon:.7f}"/>\n')
        for way_id, refs, tags in ways:
            f.write(f'<way id="{way_id}">')
            f.writelines(f'<nd ref="{ref}"/>' for ref in refs)
            f.writelines(f"<tag k={quoteattr(k)} v={quoteattr(v)}/>" for k, v in tags.items())
            f.write("</way>\n")
        f.write("</osm>\n")
    return len(ways)


def _from_extract(ox, osm_file: Path, bbox, work_dir: Path):
    xml = work_dir / "walk_extract.osm"
    try:
        extract_walk_ways(osm_file, bbox, xml)
        return ox.graph_from_xml(xml, bidirectional=True, simplify=True, retain_all=True)
    finally:
        xml.unlink(missing_ok=True)


def _undirected_largest(ox, G):
    major = int(ox.__version__.split(".")[0])
    if major >= 2:
        # largest_component needs a directed graph in osmnx 2.x, so take it before converting.
        return ox.convert.to_undirected(ox.truncate.largest_component(G, strongly=False))
    G = ox.utils_graph.get_undirected(G)
    return ox.utils_graph.get_largest_component(G, strongly=False)


def build(out_dir: Path, bbox=C.DEMO_BBOX, osm_file: Path | None = None) -> dict:
    """Download from Overpass, or read `osm_file` (a .osm.pbf extract such as Geofabrik's) when given."""
    import osmnx as ox

    t0 = time.time()
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    ox.settings.use_cache = True
    ox.settings.cache_folder = str(out_dir / "osm_cache")
    ox.settings.requests_timeout = 900       # a city-wide walk network is several Overpass queries of minutes each
    ox.settings.max_query_area_size = 4e7      # small pieces, so dense downtown tiles finish before mirrors time out
    if os.getenv("OVERPASS_URL"):              # mirrors often have no parseable /status, which costs 60 s per query
        ox.settings.overpass_url = os.environ["OVERPASS_URL"]
        ox.settings.overpass_rate_limit = False
    pbox = padded_bbox(bbox)

    G = _from_extract(ox, Path(osm_file), pbox, out_dir) if osm_file else _download(ox, pbox)
    G = ox.project_graph(G, to_crs=C.CRS_METRIC)
    G = _undirected_largest(ox, G)

    # Collapse parallel edges (keep the shortest) and drop self-loops.
    best: dict[tuple, tuple] = {}
    for a, b, data in G.edges(data=True):
        if a == b:
            continue
        key = (a, b) if str(a) < str(b) else (b, a)
        length = float(data.get("length", 0.0))
        if key not in best or length < best[key][0]:
            best[key] = (length, a, b, data)

    used = sorted({x for k in best for x in k}, key=str)
    idx = {osm: i for i, osm in enumerate(used)}
    node_x = np.array([G.nodes[o]["x"] for o in used], float)
    node_y = np.array([G.nodes[o]["y"] for o in used], float)
    node_lat, node_lon = (np.asarray(t) for t in utm_to_latlon(node_x, node_y))

    u, v, lengths, names, geoms, coords = [], [], [], [], [], []
    for length, a, b, data in best.values():
        ia, ib = idx[a], idx[b]
        geom = data.get("geometry")
        if geom is None:
            geom = LineString([(node_x[ia], node_y[ia]), (node_x[ib], node_y[ib])])
        # Orient u→v: the first vertex must be at node a.
        first = np.asarray(geom.coords[0])
        if np.hypot(*(first - [node_x[ia], node_y[ia]])) > np.hypot(*(first - [node_x[ib], node_y[ib]])):
            geom = shapely.reverse(geom)
        name = data.get("name")
        if isinstance(name, list):
            name = " / ".join(str(x) for x in name)
        xy = np.asarray(geom.coords)
        lat, lon = utm_to_latlon(xy[:, 0], xy[:, 1])
        u.append(ia), v.append(ib), lengths.append(max(length, geom.length))
        names.append(name if isinstance(name, str) else None)
        geoms.append(geom)
        coords.append(np.column_stack([lat, lon]))

    g = assemble_graph(node_lat, node_lon, node_x, node_y, u, v, lengths, names, geoms, coords, bbox=pbox)
    write_artifacts(g, out_dir, {
        "built_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "osmnx_version": ox.__version__,
        "demo_bbox": list(bbox), "pad_m": C.GRAPH_PAD_M,
        "osm_source": Path(osm_file).name if osm_file else "overpass",
    })
    return {"n_nodes": g.n_nodes, "n_edges": g.n_edges, "graph_hash": g.graph_hash,
            "seconds": round(time.time() - t0, 1)}
