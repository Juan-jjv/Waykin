import base64
import json
import os

import pytest
from starlette.websockets import WebSocketDisconnect

UPDATE = {"lat": 53.52, "lon": -113.52, "accuracy_m": 5, "ts": 1, "status": "walking", "eta_min": 10.0}


def b64(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode()


def journey(client):
    r = client.post("/api/journeys", json={})
    assert r.status_code == 201
    return r.json()


def auth(ws, role, token):
    ws.send_json({"type": "auth", "role": role, "token": token})
    return ws.receive_json()


INFO = {"viewers", "viewer_joined", "viewer_left"}   # walker-side notices added with the family work


def closed_with(ws):
    """Close code of the socket, skipping the walker's informational viewer notices."""
    with pytest.raises(WebSocketDisconnect) as e:
        while True:
            text = ws.receive_text()
            if json.loads(text).get("type") not in INFO:
                pytest.fail(f"expected a close, got {text[:80]}")
    return e.value.code


def test_plaintext_round_trip_and_late_viewer(mock_client):
    j = journey(mock_client)
    url = f"/api/relay/{j['journey_id']}"
    with mock_client.websocket_connect(url) as w:
        assert auth(w, "walker", j["walker_token"])["relay_mode"] == "plaintext"
        with mock_client.websocket_connect(url) as v:
            assert auth(v, "viewer", j["viewer_token"])["type"] == "ready"
            w.send_text(json.dumps({"type": "loc", "plain": UPDATE}))
            assert v.receive_json()["plain"]["lat"] == UPDATE["lat"]
        with mock_client.websocket_connect(url) as late:  # joins after the update: gets the latest at once
            auth(late, "viewer", j["viewer_token"])
            assert late.receive_json()["type"] == "loc"


def test_end_purges_and_notifies(mock_client):
    j = journey(mock_client)
    url = f"/api/relay/{j['journey_id']}"
    with mock_client.websocket_connect(url) as w, mock_client.websocket_connect(url) as v:
        auth(w, "walker", j["walker_token"])
        auth(v, "viewer", j["viewer_token"])
        w.send_text(json.dumps({"type": "loc", "plain": UPDATE}))
        v.receive_json()
        w.send_text(json.dumps({"type": "end", "reason": "arrived"}))
        assert v.receive_json() == {"type": "ended", "reason": "arrived"}
        assert closed_with(v) == 4410
    assert j["journey_id"] not in mock_client.app.state.waykin.journeys
    with mock_client.websocket_connect(url) as again:
        again.send_json({"type": "auth", "role": "viewer", "token": j["viewer_token"]})
        assert closed_with(again) == 4404


def test_wrong_tokens(mock_client):
    j = journey(mock_client)
    url = f"/api/relay/{j['journey_id']}"
    with mock_client.websocket_connect(url) as ws:
        ws.send_json({"type": "auth", "role": "walker", "token": j["viewer_token"]})
        assert closed_with(ws) == 4401
    with mock_client.websocket_connect("/api/relay/nope") as ws:
        ws.send_json({"type": "auth", "role": "viewer", "token": "x"})
        assert closed_with(ws) == 4404


def test_delete_needs_walker_token(mock_client):
    j = journey(mock_client)
    jid = j["journey_id"]
    r = mock_client.delete(f"/api/journeys/{jid}", headers={"Authorization": f"Bearer {j['viewer_token']}"})
    assert r.status_code == 401
    r = mock_client.delete(f"/api/journeys/{jid}", headers={"Authorization": f"Bearer {j['walker_token']}"})
    assert r.status_code == 204 and jid not in mock_client.app.state.waykin.journeys


def test_e2ee_relays_only_envelopes(e2ee_client):
    j = journey(e2ee_client)
    url = f"/api/relay/{j['journey_id']}"
    env = {"v": 1, "seq": 5, "iv": b64(os.urandom(12)), "ct": b64(os.urandom(40))}
    with e2ee_client.websocket_connect(url) as w, e2ee_client.websocket_connect(url) as v:
        auth(w, "walker", j["walker_token"])
        auth(v, "viewer", j["viewer_token"])
        raw = json.dumps({"type": "loc", "env": env})
        w.send_text(raw)
        assert v.receive_text() == raw  # byte for byte
        stored = e2ee_client.app.state.waykin.journeys.get(j["journey_id"]).latest
        assert '"lat"' not in stored
        w.send_text(json.dumps({"type": "loc", "env": {**env, "seq": 5}}))  # replayed seq
        assert closed_with(w) == 4400
    j2 = journey(e2ee_client)
    with e2ee_client.websocket_connect(f"/api/relay/{j2['journey_id']}") as w:
        auth(w, "walker", j2["walker_token"])
        w.send_text(json.dumps({"type": "loc", "plain": UPDATE}))  # plaintext in e2ee mode
        assert closed_with(w) == 4400


def test_message_too_big(mock_client):
    j = journey(mock_client)
    with mock_client.websocket_connect(f"/api/relay/{j['journey_id']}") as w:
        auth(w, "walker", j["walker_token"])
        w.send_text("x" * 70_000)
        assert closed_with(w) == 4413


def test_route_geometry_fits_the_limit(mock_client):
    """Spec v2: a long route (500 points) in a WalkerUpdate must not be rejected."""
    j = journey(mock_client)
    geom = [[53.5 + i * 1e-5, -113.5 - i * 1e-5] for i in range(500)]
    upd = {**UPDATE, "route": {"route_id": "r", "label": "fastest", "geometry": geom}}
    with mock_client.websocket_connect(f"/api/relay/{j['journey_id']}") as w:
        auth(w, "walker", j["walker_token"])
        with mock_client.websocket_connect(f"/api/relay/{j['journey_id']}") as v:
            auth(v, "viewer", j["viewer_token"])
            w.send_text(json.dumps({"type": "loc", "plain": upd}))
            assert len(v.receive_json()["plain"]["route"]["geometry"]) == 500
