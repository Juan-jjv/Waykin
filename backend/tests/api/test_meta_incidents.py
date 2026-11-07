from __future__ import annotations

from waykin import constants as C
from waykin.schemas import Meta


def test_meta_mock(client):
    r = client.get("/api/meta")
    assert r.status_code == 200
    m = Meta.model_validate(r.json())
    assert m.api_version == "1"
    assert m.relay_mode == "e2ee"
    assert m.demo_mode is False and m.demo_presets == []
    assert m.provenance.units == C.UNITS and m.provenance.disclaimer == C.DISCLAIMER
    assert m.default_radius_m == C.DEFAULT_RADIUS_M


def test_meta_plaintext_and_demo(make_client):
    c = make_client(RELAY_PLAINTEXT=True, DEMO_MODE=True)
    m = c.get("/api/meta").json()
    assert m["relay_mode"] == "plaintext"
    assert m["demo_mode"] is True
    assert [p["expected"] for p in m["demo_presets"]] == ["recommend", "abstain", "reroute"]
    assert all("hazard" not in p for p in m["demo_presets"])
    w, s, e, n = C.DEMO_BBOX
    for p in m["demo_presets"]:
        for pt in (p["origin"], p["destination"]):
            assert w <= pt["lon"] <= e and s <= pt["lat"] <= n


def test_incidents_filter(client):
    all_pts = client.get("/api/incidents").json()["points"]
    assert all_pts
    only = client.get("/api/incidents", params={"category": ["violent"]}).json()
    assert only["provenance"]["radius_m"] == C.DEFAULT_RADIUS_M
    for p in only["points"]:
        assert set(p["by_category"]) <= {"violent"}
        assert p["count"] == sum(p["by_category"].values()) > 0
    assert len(only["points"]) <= len(all_pts)


def test_incidents_bad_radius(client):
    r = client.get("/api/incidents", params={"radius_m": 75})
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "validation"


def test_ws_schemas_in_openapi(client):
    assert client.get("/api/_ws_schemas").status_code == 200
    schemas = client.get("/openapi.json").json()["components"]["schemas"]
    for name in ("WsAuth", "WsReady", "WsLoc", "WsEnd", "WsEnded", "Envelope", "WalkerUpdate",
                 "HazardSnapshot", "HazardAdded", "HazardRemoved", "WsPing", "RoutesResponse", "Error"):
        assert name in schemas, name


def test_unknown_api_path_is_error_model(client):
    r = client.get("/api/nope")
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "not_found"


def test_security_headers(client):
    r = client.get("/api/meta")
    assert r.headers["referrer-policy"] == "no-referrer"
    assert "default-src 'self'" in r.headers["content-security-policy"]
    assert r.headers["cache-control"] == "no-store"
