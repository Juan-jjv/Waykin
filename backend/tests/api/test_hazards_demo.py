from __future__ import annotations

from datetime import UTC, datetime, timedelta

from waykin import mocks
from waykin.realtime.testing import auth, close_code, new_journey

ADMIN = {"X-Admin-Token": "test-admin-token"}
HZ = {"kind": "closure", "lat": 53.52, "lon": -113.51, "radius_m": 40, "ttl_min": 5, "description": "Test closure"}


def test_hazard_auth(client):
    assert client.get("/api/hazards").status_code == 401
    assert client.get("/api/hazards", headers={"X-Admin-Token": "wrong"}).status_code == 401
    assert client.post("/api/hazards", json=HZ).json()["error"]["code"] == "forbidden"
    assert client.get("/api/hazards", headers=ADMIN).status_code == 200


def test_hazard_crud_and_mask(client):
    r = client.post("/api/hazards", json=HZ, headers=ADMIN)
    assert r.status_code == 201
    h = r.json()
    assert h["source"] == "manual" and h["edge_ids"]
    lst = client.get("/api/hazards", headers=ADMIN).json()
    assert set(h["edge_ids"]) <= set(lst["blocked_edge_ids"])
    mask = client.app.state.waykin.hazards.blocked_mask()
    assert mask[h["edge_ids"]].all()
    assert client.delete(f"/api/hazards/{h['hazard_id']}", headers=ADMIN).status_code == 204
    assert client.delete(f"/api/hazards/{h['hazard_id']}", headers=ADMIN).status_code == 404
    assert not client.app.state.waykin.hazards.blocked_mask().any()


def test_hazard_validation(client):
    assert client.post("/api/hazards", json={**HZ, "radius_m": 5}, headers=ADMIN).status_code == 422
    assert client.post("/api/hazards", json={**HZ, "description": "x" * 141}, headers=ADMIN).status_code == 422


def test_stream_snapshot_added_removed(client):
    with client.websocket_connect("/api/hazards/stream") as ws:
        snap = ws.receive_json()
        assert snap == {"type": "snapshot", "hazards": [], "blocked_edge_ids": []}
        h = client.post("/api/hazards", json={**HZ, "lat": 53.5209}, headers=ADMIN).json()
        msgs = [ws.receive_json()]
        while msgs[-1].get("hazard", {}).get("hazard_id") != h["hazard_id"]:
            msgs.append(ws.receive_json())
        client.delete(f"/api/hazards/{h['hazard_id']}", headers=ADMIN)
        m = ws.receive_json()
        while m["type"] != "hazard.removed" or m["hazard_id"] != h["hazard_id"]:
            m = ws.receive_json()
        assert m["edge_ids"] == h["edge_ids"]


def test_mock_closure_after_connect_overlaps_fixture_route(client):
    fastest = set(mocks.load("routes_recommend")["routes"][0]["edge_ids"])
    with client.websocket_connect("/api/hazards/stream") as ws:
        assert ws.receive_json()["type"] == "snapshot"
        m = ws.receive_json()
        assert m["type"] == "hazard.added"
        assert set(m["hazard"]["edge_ids"]) & fastest


def test_stream_ping(client):
    client.app.state.waykin.hazards.stream.ping_interval_s = 0.05
    client.app.state.settings.MOCK_HAZARD_DELAY_S = 60
    with client.websocket_connect("/api/hazards/stream") as ws:
        ws.receive_json()
        assert ws.receive_json() == {"type": "ping"}


def test_hazard_expiry_sweep(client):
    store = client.app.state.waykin.hazards
    h = client.post("/api/hazards", json=HZ, headers=ADMIN).json()
    store._hazards[h["hazard_id"]].expires_at = datetime.now(UTC) - timedelta(seconds=1)
    assert store.sweep_expired() == [h["hazard_id"]]
    assert store.list() == []


def test_demo_endpoints_off(client):
    assert client.post("/api/demo/reset").status_code == 404
    assert client.post("/api/demo/trigger/reroute").status_code == 404


def test_demo_trigger_and_reset(make_client):
    c = make_client(DEMO_MODE=True)
    assert c.get("/api/hazards").status_code == 200  # no token needed in demo mode
    h1 = c.post("/api/demo/trigger/reroute").json()
    h2 = c.post("/api/demo/trigger/reroute").json()
    assert h1["source"] == "demo" and h1["hazard_id"] == h2["hazard_id"] == "hz_demo_reroute"
    assert h1["edge_ids"] == h2["edge_ids"]
    exp = datetime.fromisoformat(h2["expires_at"]) - datetime.fromisoformat(h2["created_at"])
    assert exp == timedelta(minutes=10)
    assert len(c.get("/api/hazards").json()["hazards"]) == 1
    assert c.post("/api/demo/trigger/recommend").status_code == 404  # no scripted closure

    j = new_journey(c)
    with c.websocket_connect(f"/api/relay/{j['journey_id']}") as v:
        auth(v, "viewer", j["viewer_token"])
        assert c.post("/api/demo/reset").status_code == 204
        assert v.receive_json()["type"] == "ended"
        assert close_code(v) == 4410
    st = c.app.state.waykin
    assert st.hazards.list() == [] and len(st.journeys) == 0 and st.relay.socket_count() == 0
