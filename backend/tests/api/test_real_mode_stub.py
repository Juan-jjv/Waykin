"""Real mode on the grid graph and synthetic test bundle, using A3's Phase 1 service.plan stub."""
from waykin import schemas as S


def test_routes_through_service_plan(real_client, real_state):
    g = real_state.graph
    body = {"origin": {"lat": float(g.node_lat[0]), "lon": float(g.node_lon[0])},
            "destination": {"lat": float(g.node_lat[100]), "lon": float(g.node_lon[100])}}
    r = real_client.post("/api/routes", json=body)
    assert r.status_code == 200, r.text
    resp = S.RoutesResponse.model_validate(r.json())
    assert resp.provenance.source == "synthetic" and resp.routes[0].label == "fastest"


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
