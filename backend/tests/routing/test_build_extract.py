"""Reading streets from an OpenStreetMap extract instead of Overpass. The tiny map below is made up."""
import xml.etree.ElementTree as ET

import numpy as np
import pytest

from waykin.routing.build import drive_directions, drive_kmh, extract_walk_ways, is_drivable, is_walkable, way_modes

BBOX = (-113.52, 53.51, -113.50, 53.53)

TINY_MAP = """<?xml version="1.0" encoding="UTF-8"?>
<osm version="0.6">
  <node id="1" lat="53.520" lon="-113.510"/>
  <node id="2" lat="53.521" lon="-113.510"/>
  <node id="3" lat="53.522" lon="-113.510"/>
  <node id="4" lat="53.600" lon="-113.400"/>
  <node id="5" lat="53.601" lon="-113.400"/>
  <node id="6" lat="53.540" lon="-113.510"/>
  <way id="10"><nd ref="1"/><nd ref="2"/><tag k="highway" v="footway"/><tag k="name" v="A &amp; B"/></way>
  <way id="11"><nd ref="2"/><nd ref="3"/><tag k="highway" v="motorway"/></way>
  <way id="12"><nd ref="1"/><nd ref="3"/><tag k="highway" v="service"/><tag k="access" v="private"/></way>
  <way id="13"><nd ref="4"/><nd ref="5"/><tag k="highway" v="residential"/></way>
  <way id="14"><nd ref="3"/><nd ref="6"/><tag k="highway" v="residential"/></way>
  <way id="15"><nd ref="1"/><nd ref="2"/><tag k="building" v="yes"/></way>
</osm>
"""


@pytest.mark.parametrize("tags, ok", [
    ({"highway": "footway"}, True),
    ({"highway": "residential", "sidewalk": "both"}, True),
    ({"highway": "motorway_link"}, False),
    ({"highway": "cycleway"}, False),
    ({"highway": "path", "foot": "no"}, False),
    ({"highway": "service", "access": "private"}, False),
    ({"highway": "primary", "sidewalk": "separate"}, False),
    ({"building": "yes"}, False),
])
def test_walk_filter_matches_osmnx_walk_rules(tags, ok):
    assert is_walkable(tags) is ok


@pytest.mark.parametrize("tags, ok", [
    ({"highway": "residential"}, True),
    ({"highway": "motorway"}, True),
    ({"highway": "footway"}, False),
    ({"highway": "service"}, False),
    ({"highway": "residential", "access": "private"}, False),
    ({"highway": "residential", "motor_vehicle": "no"}, False),
    ({"building": "yes"}, False),
])
def test_drive_filter_matches_osmnx_drive_rules(tags, ok):
    assert is_drivable(tags) is ok


@pytest.mark.parametrize("tags, dirs", [
    ({"highway": "residential"}, (True, True)),
    ({"highway": "residential", "oneway": "yes"}, (True, False)),
    ({"highway": "residential", "oneway": "-1"}, (False, True)),
    ({"highway": "primary", "junction": "roundabout"}, (True, False)),
    ({"highway": "motorway"}, (True, False)),
    ({"highway": "motorway", "oneway": "no"}, (True, True)),
])
def test_drive_directions(tags, dirs):
    assert drive_directions(tags) == dirs


@pytest.mark.parametrize("tags, kmh", [
    ({"highway": "residential"}, 40.0),
    ({"highway": "motorway"}, 100.0),
    ({"highway": "primary", "maxspeed": "70"}, 70.0),
    ({"highway": "primary", "maxspeed": "30 mph"}, pytest.approx(48.28, abs=0.01)),
    ({"highway": "primary", "maxspeed": "signals"}, 60.0),
])
def test_drive_kmh(tags, kmh):
    assert drive_kmh(tags) == kmh


def test_way_modes():
    assert way_modes({"highway": "footway"}) == {"wk_walk": "1", "wk_dfwd": "0", "wk_drev": "0", "wk_kmh": "40"}
    assert way_modes({"highway": "motorway"}) == {"wk_walk": "0", "wk_dfwd": "1", "wk_drev": "0", "wk_kmh": "100"}
    assert way_modes({"highway": "service", "access": "private"}) is None


def test_extract_keeps_walkable_or_drivable_ways_touching_the_box(tmp_path):
    pytest.importorskip("osmium")
    src = tmp_path / "tiny.osm"
    src.write_text(TINY_MAP, encoding="utf-8")
    out = tmp_path / "walk.osm"
    assert extract_walk_ways(src, BBOX, out) == 3
    root = ET.parse(out).getroot()
    assert sorted(int(w.get("id")) for w in root.iter("way")) == [10, 11, 14]
    assert sorted(int(n.get("id")) for n in root.iter("node")) == [1, 2, 3, 6]   # 6 lies outside but ends way 14
    modes = {int(w.get("id")): {t.get("k"): t.get("v") for t in w.iter("tag") if t.get("k").startswith("wk_")}
             for w in root.iter("way")}
    assert modes[10] == {"wk_walk": "1", "wk_dfwd": "0", "wk_drev": "0", "wk_kmh": "40"}
    assert modes[11] == {"wk_walk": "0", "wk_dfwd": "1", "wk_drev": "0", "wk_kmh": "100"}
    assert modes[14] == {"wk_walk": "1", "wk_dfwd": "1", "wk_drev": "1", "wk_kmh": "40"}
    names = [t.get("v") for t in root.iter("tag") if t.get("k") == "name"]
    assert names == ["A & B"]


def test_build_from_extract_keeps_modes_per_edge(tmp_path):
    """Footway 1-2 (walk only), motorway 2→3 (drive one way only), residential 3-6 (both)."""
    pytest.importorskip("osmium")
    pytest.importorskip("osmnx")
    from waykin.routing.build import build
    from waykin.routing.graph import load_graph

    src = tmp_path / "tiny.osm"
    src.write_text(TINY_MAP, encoding="utf-8")
    build(tmp_path / "graph", bbox=BBOX, osm_file=src)
    g = load_graph(tmp_path / "graph")
    assert g.n_edges == 3
    by_len = np.argsort(g.edge_length_m)        # 1-2 and 2-3 are ~111 m, 3-6 ~2 km
    long_edge = int(by_len[-1])
    assert g.edge_walk[long_edge] and g.edge_drive_fwd[long_edge] and g.edge_drive_rev[long_edge]

    def lat(node):
        return round(float(g.node_lat[node]), 3)

    foot = [e for e in range(3) if not (g.edge_drive_fwd[e] or g.edge_drive_rev[e])]
    motor = [e for e in range(3) if not g.edge_walk[e]]
    assert len(foot) == 1 and len(motor) == 1
    m = motor[0]
    # The motorway runs north from node 2 (53.521) to node 3 (53.522) and may only be driven that way.
    north_end = g.edge_v[m] if lat(g.edge_v[m]) > lat(g.edge_u[m]) else g.edge_u[m]
    assert lat(north_end) == 53.522
    assert bool(g.edge_drive_fwd[m]) == (g.edge_v[m] == north_end)
    assert bool(g.edge_drive_rev[m]) == (g.edge_u[m] == north_end)
