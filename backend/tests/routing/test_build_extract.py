"""Reading streets from an OpenStreetMap extract instead of Overpass. The tiny map below is made up."""
import xml.etree.ElementTree as ET

import pytest

from waykin.routing.build import extract_walk_ways, is_walkable

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


def test_extract_keeps_walkable_ways_touching_the_box(tmp_path):
    pytest.importorskip("osmium")
    src = tmp_path / "tiny.osm"
    src.write_text(TINY_MAP, encoding="utf-8")
    out = tmp_path / "walk.osm"
    assert extract_walk_ways(src, BBOX, out) == 2
    root = ET.parse(out).getroot()
    assert sorted(int(w.get("id")) for w in root.iter("way")) == [10, 14]
    assert sorted(int(n.get("id")) for n in root.iter("node")) == [1, 2, 3, 6]   # 6 lies outside but ends way 14
    names = [t.get("v") for t in root.iter("tag") if t.get("k") == "name"]
    assert names == ["A & B"]
