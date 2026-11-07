"""Demo controls and the full loop a judge sees (A4, H24-H29), on mock fixtures:
plan -> start a journey -> family follows -> scripted closure -> client reroutes -> arrive -> purged."""
import base64
import json
import os

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from waykin.config import Settings
from waykin.main import create_app


def b64(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode()


def env(seq: int) -> dict:
    return {"v": 1, "seq": seq, "iv": b64(os.urandom(12)), "ct": b64(os.urandom(48))}


def closed_with(ws) -> int:
    with pytest.raises(WebSocketDisconnect) as e:
        while True:
            ws.receive_text()
    return e.value.code


@pytest.fixture
def demo_client():
    with TestClient(create_app(Settings(WAYKIN_MOCK=True, DEMO_MODE=True, ADMIN_TOKEN="admin"))) as c:
        yield c


def test_demo_endpoints_404_when_demo_mode_off(mock_client):
    for path in ("/api/demo/reset", "/api/demo/trigger/mock-reroute"):
        r = mock_client.post(path)
        assert r.status_code == 404 and r.json()["error"]["code"] == "not_found"


def test_trigger_unknown_and_no_closure(demo_client):
    assert demo_client.post("/api/demo/trigger/nope").status_code == 404
    r = demo_client.post("/api/demo/trigger/mock-recommend")
    assert r.status_code == 422 and r.json()["error"]["code"] == "validation"


def test_trigger_replaces_earlier_demo_closure(demo_client):
    a = demo_client.post("/api/demo/trigger/mock-reroute").json()
    b = demo_client.post("/api/demo/trigger/mock-reroute").json()
    ids = [h["hazard_id"] for h in demo_client.get("/api/hazards").json()["hazards"]]
    assert ids == [b["hazard_id"]] and a["hazard_id"] != b["hazard_id"]
    assert b["source"] == "demo"


def test_reset_clears_hazards_and_journeys(demo_client):
    demo_client.post("/api/demo/trigger/mock-reroute")
    demo_client.post("/api/journeys", json={})
    assert demo_client.post("/api/demo/reset").status_code == 204
    st = demo_client.app.state.waykin
    assert st.hazards.list() == [] and len(st.journeys) == 0


def test_full_demo_loop(demo_client):
    c = demo_client
    meta = c.get("/api/meta").json()
    assert meta["demo_mode"] is True
    p = next(x for x in meta["demo_presets"] if x["expected"] == "reroute")
    assert "hazard" not in p  # the scripted closure is not part of the public contract

    # 1. plan
    r = c.post("/api/routes", json={"origin": p["origin"], "destination": p["destination"]})
    assert r.status_code == 200
    route = r.json()["routes"][0]

    # 2. start a journey; the family viewer follows
    j = c.post("/api/journeys", json={}).json()
    url = f"/api/relay/{j['journey_id']}"
    with c.websocket_connect(url) as w, c.websocket_connect(url) as v, \
            c.websocket_connect("/api/hazards/stream") as hs:
        w.send_json({"type": "auth", "role": "walker", "token": j["walker_token"]})
        assert w.receive_json()["type"] == "ready"
        v.send_json({"type": "auth", "role": "viewer", "token": j["viewer_token"]})
        assert v.receive_json()["relay_mode"] == "e2ee"
        assert hs.receive_json() == {"type": "snapshot", "hazards": [], "blocked_edge_ids": []}

        raw = json.dumps({"type": "loc", "env": env(1)})
        w.send_text(raw)
        assert v.receive_text() == raw

        # 3. the presenter triggers the closure; every client hears about it on the public stream
        h = c.post("/api/demo/trigger/" + p["id"])
        assert h.status_code == 201
        added = hs.receive_json()
        assert added["type"] == "hazard.added" and added["hazard"]["hazard_id"] == h.json()["hazard_id"]
        blocked = set(added["hazard"]["edge_ids"])
        assert blocked & set(route["edge_ids"]), "the closure must land on the planned route"

        # 4. the client (not the server) sees it is affected and asks for an anonymous reroute
        here = {"lat": route["geometry"][1][0], "lon": route["geometry"][1][1]}
        rr = c.post("/api/routes/reroute", json={"position": here, "destination": p["destination"]})
        assert rr.status_code == 200
        assert not blocked & {e for x in rr.json()["routes"] for e in x["edge_ids"]}

        raw2 = json.dumps({"type": "loc", "env": env(2)})
        w.send_text(raw2)
        assert v.receive_text() == raw2

        # 5. arrive: the viewer is told, every socket closes, nothing is kept
        w.send_json({"type": "end", "reason": "arrived"})
        assert v.receive_json() == {"type": "ended", "reason": "arrived"}
        assert closed_with(v) == 4410

    st = c.app.state.waykin
    assert j["journey_id"] not in st.journeys and j["journey_id"] not in st.relay.rooms
    assert c.post("/api/demo/reset").status_code == 204
    assert c.get("/api/hazards").json() == {"hazards": [], "blocked_edge_ids": []}
