from __future__ import annotations

import pytest

from waykin import mocks
from waykin.schemas import RoutesResponse

DEST = {"lat": 53.52, "lon": -113.50}


def _post(c, lat, path="/api/routes", key="origin", **extra):
    return c.post(path, json={key: {"lat": lat, "lon": -113.52}, "destination": DEST, **extra})


def test_mock_parity_selects_fixture(client):
    rec = _post(client, 53.5200)
    ab = _post(client, 53.5201)
    assert rec.status_code == ab.status_code == 200
    rec, ab = RoutesResponse.model_validate(rec.json()), RoutesResponse.model_validate(ab.json())
    assert rec.decision.status == "recommend" and rec.decision.recommended_route_id
    assert rec.decision.recommended_route_id != rec.routes[0].route_id
    assert ab.decision.status == "abstain" and ab.decision.reason == "indistinguishable"
    assert [r.label for r in rec.routes] == ["fastest", "balanced", "lower_exposure"]


def test_radius_echoed_in_provenance(client):
    r = _post(client, 53.52, radius_m=200).json()
    assert r["provenance"]["radius_m"] == 200


def test_reroute_uses_position(client):
    r = _post(client, 53.5201, path="/api/routes/reroute", key="position")
    assert r.status_code == 200
    assert r.json()["decision"]["reason"] == "indistinguishable"
    assert r.headers["cache-control"] == "no-store"
    assert "set-cookie" not in r.headers


@pytest.mark.parametrize("extra", [{"journey_id": "abc"}, {"token": "abc"}, {"walker_token": "x"}])
def test_reroute_rejects_identifiers(client, extra):
    r = _post(client, 53.52, path="/api/routes/reroute", key="position", **extra)
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "validation"


def test_validation_message_has_no_coordinates(client):
    r = client.post("/api/routes", json={"origin": {"lat": 123.45678, "lon": -113.52}, "destination": DEST})
    assert r.status_code == 422
    body = r.text
    assert "123.45678" not in body and "113.52" not in body


def test_mock_closure_triggers_rerouted_fixture(client):
    from waykin.api.hazards import add_mock_closure

    state = client.app.state.waykin
    h = add_mock_closure(state)
    fastest = mocks.load("routes_recommend")["routes"][0]["edge_ids"]
    assert set(h.edge_ids) & set(fastest)
    r = _post(client, 53.52, path="/api/routes/reroute", key="position").json()
    assert r["blocked_edge_count"] >= 1
    assert not set(r["routes"][0]["edge_ids"]) & set(h.edge_ids)


def test_real_routes_on_grid(make_client, real_state):
    c = make_client(state=real_state, WAYKIN_MOCK=False)
    g = real_state.graph
    o = {"lat": float(g.node_lat[0]), "lon": float(g.node_lon[0])}
    d = {"lat": float(g.node_lat[-1]), "lon": float(g.node_lon[-1])}
    try:
        r = c.post("/api/routes", json={"origin": o, "destination": d})
    except NotImplementedError:
        pytest.skip("routing.service.plan not implemented yet")
    assert r.status_code == 200, r.text
    RoutesResponse.model_validate(r.json())
    far = c.post("/api/routes", json={"origin": {"lat": 10.0, "lon": 10.0}, "destination": d})
    assert far.status_code == 422 and far.json()["error"]["code"] == "outside_area"
