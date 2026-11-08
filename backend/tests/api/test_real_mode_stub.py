"""Real mode on the grid graph and synthetic test bundle, using A3's Phase 1 service.plan stub."""
from waykin import constants as C
from waykin import schemas as S


def test_routes_through_service_plan(real_client, real_state):
    g = real_state.graph
    body = {"origin": {"lat": float(g.node_lat[0]), "lon": float(g.node_lon[0])},
            "destination": {"lat": float(g.node_lat[100]), "lon": float(g.node_lon[100])}}
    r = real_client.post("/api/routes", json=body)
    assert r.status_code == 200, r.text
    resp = S.RoutesResponse.model_validate(r.json())
    assert resp.provenance.source == "synthetic" and resp.routes[0].label == "fastest"
    # Walking counts the reports the map shows (30 days); driving keeps the 7-day allocation model.
    assert resp.provenance.window_days == C.WINDOW_DAYS == 30
    assert resp.provenance.units == C.WALK_UNITS
    drive = S.RoutesResponse.model_validate(real_client.post("/api/routes", json={**body, "mode": "drive"}).json())
    assert drive.provenance.window_days == C.ROUTE_WINDOW_DAYS == 7
    assert drive.provenance.units.endswith("last 7 days")


def test_outside_area_error_has_no_coordinates(real_client):
    r = real_client.post("/api/routes", json={"origin": {"lat": 53.6123, "lon": -113.4}, "destination":
                                              {"lat": 53.52, "lon": -113.51}})
    assert r.status_code == 422 and r.json()["error"]["code"] == "outside_area"
    assert "53.6123" not in r.text


def test_meta_and_incidents_from_bundle(real_client, real_state):
    m = real_client.get("/api/meta").json()
    assert m["radii"] == [100] and m["provenance"]["source_label"] == "Synthetic data (demo)"
    pts = real_client.get("/api/incidents").json()["points"]
    assert len(pts) == len(real_state.exposure.locations)


def test_incidents_date_window(real_client, real_state):
    full = real_client.get("/api/incidents", params={"days": C.WINDOW_DAYS}).json()
    week = real_client.get("/api/incidents", params={"days": 7, "category": "assault"}).json()
    assert full["provenance"]["window_days"] == C.WINDOW_DAYS and week["provenance"]["window_days"] == 7
    assert sum(p["count"] for p in full["points"]) == int(real_state.exposure.locations["count"].sum())
    assert 0 < sum(p["count"] for p in week["points"]) < sum(p["count"] for p in full["points"])
    assert all(set(p["by_category"]) == {"assault"} for p in week["points"])
    assert real_client.get("/api/incidents", params={"days": 0}).status_code == 422


def test_drive_mode_routes_and_reroute(real_client, real_state):
    g = real_state.graph
    a = {"lat": float(g.node_lat[0]), "lon": float(g.node_lon[0])}
    b = {"lat": float(g.node_lat[100]), "lon": float(g.node_lon[100])}
    assert real_client.get("/api/meta").json()["modes"] == ["walk", "drive"]
    walk = real_client.post("/api/routes", json={"origin": a, "destination": b}).json()
    drive = real_client.post("/api/routes", json={"origin": a, "destination": b, "mode": "drive"}).json()
    assert walk["mode"] == "walk" and drive["mode"] == "drive"
    assert drive["routes"][0]["minutes"] < walk["routes"][0]["minutes"]
    assert "by car" in drive["routes"][0]["explanation"]
    again = real_client.post("/api/routes/reroute", json={"position": a, "destination": b, "mode": "drive"})
    assert again.status_code == 200 and again.json()["mode"] == "drive"
    bad = real_client.post("/api/routes", json={"origin": a, "destination": b, "mode": "fly"})
    assert bad.status_code == 422 and bad.json()["error"]["code"] == "validation"
