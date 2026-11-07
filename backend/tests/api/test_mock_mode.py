from waykin import constants as C
from waykin import schemas as S


def test_meta(mock_client):
    m = S.Meta.model_validate(mock_client.get("/api/meta").json())
    assert m.provenance.units == C.UNITS and m.provenance.disclaimer == C.DISCLAIMER
    assert m.relay_mode == "plaintext" and m.demo_presets == []


def test_routes_fixture_by_latitude_parity(mock_client):
    body = {"destination": {"lat": 53.52, "lon": -113.51}}
    a = mock_client.post("/api/routes", json={"origin": {"lat": 53.5160, "lon": -113.52}, **body}).json()
    b = mock_client.post("/api/routes", json={"origin": {"lat": 53.5161, "lon": -113.52}, **body}).json()
    assert {a["decision"]["status"], b["decision"]["status"]} == {"recommend", "abstain"}
    for r in (a, b):
        S.RoutesResponse.model_validate(r)
        assert r["provenance"]["source"] == "synthetic"
        assert r["decision"]["recommended_route_id"] != r["routes"][0]["route_id"]


def test_routes_rejects_extra_fields_without_echoing_coordinates(mock_client):
    r = mock_client.post("/api/routes", json={"origin": {"lat": 53.51234, "lon": -113.52}, "destination":
                                              {"lat": 53.52, "lon": -113.51}, "journey_id": "x"})
    assert r.status_code == 422 and r.json()["error"]["code"] == "validation"
    assert "53.51234" not in r.text


def test_reroute_takes_no_journey_or_token(mock_client):
    ok = mock_client.post("/api/routes/reroute", json={"position": {"lat": 53.52, "lon": -113.52},
                                                       "destination": {"lat": 53.52, "lon": -113.51}})
    assert ok.status_code == 200 and "set-cookie" not in ok.headers
    bad = mock_client.post("/api/routes/reroute", json={"position": {"lat": 53.52, "lon": -113.52},
                                                        "destination": {"lat": 53.52, "lon": -113.51}, "token": "t"})
    assert bad.status_code == 422


def test_incidents_category_filter(mock_client):
    all_pts = mock_client.get("/api/incidents").json()["points"]
    theft = mock_client.get("/api/incidents", params={"category": "assault"}).json()["points"]
    assert len(theft) < len(all_pts)
    assert all(set(p) == {"location_id", "lat", "lon", "count", "by_category"} for p in all_pts)


def test_hazard_fixture_overlaps_a_fixture_route(mock_client):
    from waykin.api.deps import mock
    hz = set(mock("hazard_closure")["edge_ids"])
    rec = mock("routes_recommend")
    recommended = [r for r in rec["routes"] if r["route_id"] == rec["decision"]["recommended_route_id"]][0]
    assert hz & set(recommended["edge_ids"])
    assert not hz & set(mock("routes_reroute")["routes"][0]["edge_ids"])


def test_hazards_public_get_admin_post(mock_client):
    assert mock_client.get("/api/hazards").status_code == 200
    req = {"kind": "closure", "lat": 53.52, "lon": -113.52, "description": "test"}
    assert mock_client.post("/api/hazards", json=req).status_code == 403
    r = mock_client.post("/api/hazards", json=req, headers={"X-Admin-Token": "admin"})
    assert r.status_code == 201 and r.json()["edge_ids"]
    assert mock_client.get("/api/hazards").json()["blocked_edge_ids"] == sorted(r.json()["edge_ids"])


def test_hazard_stream_snapshot(mock_client):
    with mock_client.websocket_connect("/api/hazards/stream") as ws:
        assert ws.receive_json()["type"] == "snapshot"


def test_security_headers(mock_client):
    r = mock_client.post("/api/routes", json={"origin": {"lat": 53.516, "lon": -113.52},
                                              "destination": {"lat": 53.52, "lon": -113.51}})
    assert r.headers["cache-control"] == "no-store"
    assert r.headers["referrer-policy"] == "no-referrer"
    assert "https://tiles.openfreemap.org" in r.headers["content-security-policy"]


def test_openapi_includes_ws_schemas(mock_client):
    spec = mock_client.get("/openapi.json").json()
    for name in ("Envelope", "WalkerUpdate", "HazardAdded", "WsSchemas", "RoutesResponse"):
        assert name in spec["components"]["schemas"]
