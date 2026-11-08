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


# osmnx's "drive" network filter.
_DRIVE_EXCLUDE = {
    "highway": re.compile("abandoned|bridleway|bus_guideway|construction|corridor|cycleway|elevator|escalator|footway|"
                          "no|path|pedestrian|planned|platform|proposed|raceway|razed|rest_area|service|services|steps|"
                          "track"),
    "area": re.compile("yes"), "access": re.compile("private"), "motor_vehicle": re.compile("no"),
    "motorcar": re.compile("no"),
    "service": re.compile("alley|driveway|emergency_access|parking|parking_aisle|private"),
}

# Free-flow speed when a way has no usable maxspeed tag. Edmonton's default on residential streets is 40 km/h.
DEFAULT_KMH = {
    "motorway": 100.0, "motorway_link": 60.0, "trunk": 80.0, "trunk_link": 50.0,
    "primary": 60.0, "primary_link": 40.0, "secondary": 60.0, "secondary_link": 40.0,
    "tertiary": 50.0, "tertiary_link": 40.0, "unclassified": 40.0, "residential": 40.0, "living_street": 20.0,
}
FALLBACK_KMH = 40.0
_NUMBER = re.compile(r"\d+(?:\.\d+)?")


def is_drivable(tags: dict[str, str]) -> bool:
    if "highway" not in tags:
        return False
    return not any(key in tags and pattern.search(tags[key]) for key, pattern in _DRIVE_EXCLUDE.items())


def drive_directions(tags: dict[str, str]) -> tuple[bool, bool]:
    """(along the way's node order, against it) for a drivable way."""
    oneway = tags.get("oneway", "").strip().lower()
    if oneway in ("yes", "true", "1"):
        return True, False
    if oneway in ("-1", "reverse"):
        return False, True
    if oneway == "no":
        return True, True
    if tags.get("junction") in ("roundabout", "circular") or tags.get("highway") in ("motorway", "motorway_link"):
        return True, False
    return True, True


def drive_kmh(tags: dict[str, str]) -> float:
    raw = tags.get("maxspeed", "")
    match = _NUMBER.search(raw)
    if match:
        kmh = float(match.group()) * (1.609344 if "mph" in raw else 1.0)
        if 5.0 <= kmh <= 130.0:
            return kmh
    return DEFAULT_KMH.get(tags.get("highway", ""), FALLBACK_KMH)


def way_modes(tags: dict[str, str]) -> dict[str, str] | None:
    """The WayKin tags for a way (walk, drive along/against node order, km/h), or None if neither mode may use it."""
    walk, drive = is_walkable(tags), is_drivable(tags)
    if not (walk or drive):
        return None
    fwd, rev = drive_directions(tags) if drive else (False, False)
    kmh = drive_kmh(tags) if drive else FALLBACK_KMH
    return {"wk_walk": "1" if walk else "0", "wk_dfwd": "1" if fwd else "0", "wk_drev": "1" if rev else "0",
            "wk_kmh": f"{kmh:g}"}


MODE_TAGS = ["wk_walk", "wk_dfwd", "wk_drev", "wk_kmh"]


def extract_ways(osm_file: Path, bbox, xml_out: Path) -> int:
    """Write the walkable or drivable ways touching `bbox` (with all their nodes) from a .osm.pbf extract as OSM XML.

    Each way gets the `way_modes` tags, so the graph knows which edges each travel mode may use."""
    import osmium

    w, s, e, n = bbox
    nodes: dict[int, tuple[float, float]] = {}
    ways: list[tuple[int, list[int], dict[str, str]]] = []
    processor = (osmium.FileProcessor(str(osm_file)).with_locations()
                 .with_filter(osmium.filter.EntityFilter(osmium.osm.WAY)))
    for way in processor:
        tags = {t.k: t.v for t in way.tags}
        modes = way_modes(tags)
        if modes is None:
            continue
        tags.update(modes)
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


def extract_walk_ways(osm_file: Path, bbox, xml_out: Path) -> int:
    """Back-compat name: the extract now holds every walkable or drivable way."""
    return extract_ways(osm_file, bbox, xml_out)


def mark_directed_modes(G) -> None:
    """Give every directed edge `wk_go` (a car may travel it in this direction) and `wk_class` (the mode tags that
    don't depend on direction). Edges without WayKin tags (an Overpass walk download) are walk-only.

    osmnx's bidirectional loader keeps each way's node order on the forward copy and sets `reversed` on the other."""
    for _, _, data in G.edges(data=True):
        walk = data.get("wk_walk", "1") == "1"
        fwd, rev = data.get("wk_dfwd", "0") == "1", data.get("wk_drev", "0") == "1"
        kmh = data.get("wk_kmh", f"{FALLBACK_KMH:g}")
        data["wk_go"] = rev if data.get("reversed", False) else fwd
        data["wk_class"] = f"{int(walk)}{int(fwd or rev)}{int(fwd != rev)}:{kmh}"


def _from_extract(ox, osm_file: Path, bbox, work_dir: Path):
    xml = work_dir / "walk_extract.osm"
    tags = list(ox.settings.useful_tags_way)
    try:
        extract_ways(osm_file, bbox, xml)
        ox.settings.useful_tags_way = tags + [t for t in MODE_TAGS if t not in tags]
        G = ox.graph_from_xml(xml, bidirectional=True, simplify=False, retain_all=True)
    finally:
        ox.settings.useful_tags_way = tags
        xml.unlink(missing_ok=True)
    mark_directed_modes(G)
    # Only merge edges with the same modes; a merged edge is drivable one way only if every piece of it is.
    return ox.simplify_graph(G, edge_attrs_differ=["wk_class"],
                             edge_attr_aggs={"length": sum, "travel_time": sum, "wk_go": all})


def _largest(ox, G):
    major = int(ox.__version__.split(".")[0])
    if major >= 2:
        return ox.truncate.largest_component(G, strongly=False)
    return ox.utils_graph.get_largest_component(G, strongly=False)


def _flag(value) -> bool:
    """A merged attribute is a list of the distinct values: all must hold."""
    return all(value) if isinstance(value, list) else bool(value)


def _kmh(value) -> float:
    values = value if isinstance(value, list) else [value]
    return min(float(v) for v in values)


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

    if osm_file:
        G = _from_extract(ox, Path(osm_file), pbox, out_dir)
    else:
        G = _download(ox, pbox)
        mark_directed_modes(G)
    G = ox.project_graph(G, to_crs=C.CRS_METRIC)
    G = _largest(ox, G)

    # Collapse both directions and any parallel edges into one undirected edge (geometry of the shortest), drop
    # self-loops, and remember which modes may use it: walking either way, driving per direction.
    best: dict[tuple, tuple] = {}
    walk_ok: dict[tuple, bool] = {}
    drive_ok: dict[tuple, bool] = {}          # keyed by the DIRECTED pair
    kmh_of: dict[tuple, float] = {}
    for a, b, data in G.edges(data=True):
        if a == b:
            continue
        key = (a, b) if str(a) < str(b) else (b, a)
        length = float(data.get("length", 0.0))
        if key not in best or length < best[key][0]:
            best[key] = (length, a, b, data)
        walk_ok[key] = walk_ok.get(key, False) or str(data.get("wk_class", "1"))[0] == "1"
        if _flag(data.get("wk_go", False)):
            drive_ok[(a, b)] = True
            kmh_of[key] = max(kmh_of.get(key, 0.0), _kmh(data.get("wk_kmh", FALLBACK_KMH)))

    used = sorted({x for k in best for x in k}, key=str)
    idx = {osm: i for i, osm in enumerate(used)}
    node_x = np.array([G.nodes[o]["x"] for o in used], float)
    node_y = np.array([G.nodes[o]["y"] for o in used], float)
    node_lat, node_lon = (np.asarray(t) for t in utm_to_latlon(node_x, node_y))

    u, v, lengths, names, geoms, coords = [], [], [], [], [], []
    walk, drive_fwd, drive_rev, kmh = [], [], [], []
    for key, (length, a, b, data) in best.items():
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
        walk.append(walk_ok[key])
        drive_fwd.append(drive_ok.get((a, b), False))
        drive_rev.append(drive_ok.get((b, a), False))
        kmh.append(kmh_of.get(key, FALLBACK_KMH))

    g = assemble_graph(node_lat, node_lon, node_x, node_y, u, v, lengths, names, geoms, coords, bbox=pbox,
                       edge_walk=walk, edge_drive_fwd=drive_fwd, edge_drive_rev=drive_rev, edge_drive_kmh=kmh)
    write_artifacts(g, out_dir, {
        "built_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "osmnx_version": ox.__version__,
        "demo_bbox": list(bbox), "pad_m": C.GRAPH_PAD_M,
        "osm_source": Path(osm_file).name if osm_file else "overpass",
    })
    return {"n_nodes": g.n_nodes, "n_edges": g.n_edges, "graph_hash": g.graph_hash,
            "walk_edges": int(g.edge_walk.sum()), "drive_edges": int((g.edge_drive_fwd | g.edge_drive_rev).sum()),
            "seconds": round(time.time() - t0, 1)}
