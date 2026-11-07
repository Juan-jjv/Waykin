from __future__ import annotations

import json

import pytest

from waykin.realtime.testing import auth, close_code, fake_env, new_journey, send, walker_update


def _ws(c, jid):
    return c.websocket_connect(f"/api/relay/{jid}")


def test_create_journey_defaults(client):
    j = new_journey(client)
    assert set(j) == {"journey_id", "walker_token", "viewer_token", "expires_at", "relay_mode"}
    assert j["relay_mode"] == "e2ee"
    stored = client.app.state.waykin.journeys.get(j["journey_id"])
    assert stored.walker_token_hash != j["walker_token"].encode()
    assert j["walker_token"] not in repr(stored)


@pytest.mark.parametrize("ttl", [5, 241])
def test_create_journey_ttl_bounds(client, ttl):
    r = client.post("/api/journeys", json={"expires_in_min": ttl})
    assert r.status_code == 422


def test_e2ee_relay_walker_to_viewer(client):
    j = new_journey(client)
    jid = j["journey_id"]
    with _ws(client, jid) as w, _ws(client, jid) as v:
        ready = auth(w, "walker", j["walker_token"])
        assert ready["type"] == "ready" and ready["relay_mode"] == "e2ee"
        assert auth(v, "viewer", j["viewer_token"])["type"] == "ready"
        msg = json.dumps({"type": "loc", "env": fake_env(1)})
        w.send_text(msg)
        assert v.receive_text() == msg  # byte for byte
        # a late viewer immediately gets the latest message
        with _ws(client, jid) as v2:
            auth(v2, "viewer", j["viewer_token"])
            assert v2.receive_text() == msg
        # stale seq is dropped, newer seq goes through
        send(w, {"type": "loc", "env": fake_env(1)})
        newer = json.dumps({"type": "loc", "env": fake_env(2)})
        w.send_text(newer)
        assert v.receive_text() == newer
        send(w, {"type": "end", "reason": "arrived"})
        assert v.receive_json() == {"type": "ended", "reason": "arrived"}
        assert close_code(v) == 4410
    assert jid not in client.app.state.waykin.journeys


def test_plaintext_mode(make_client):
    c = make_client(RELAY_PLAINTEXT=True)
    j = new_journey(c)
    with _ws(c, j["journey_id"]) as w, _ws(c, j["journey_id"]) as v:
        assert auth(w, "walker", j["walker_token"])["relay_mode"] == "plaintext"
        auth(v, "viewer", j["viewer_token"])
        send(w, {"type": "loc", "plain": walker_update()})
        assert v.receive_json()["plain"]["status"] == "walking"
        send(w, {"type": "loc", "env": fake_env(5)})
        assert close_code(w) == 4400


@pytest.mark.parametrize("msg", [
    {"type": "loc", "plain": walker_update()},
    {"type": "loc", "env": fake_env(1), "plain": walker_update()},
    {"type": "loc", "env": {**fake_env(1), "lat": 53.5}},
    {"type": "loc", "env": {**fake_env(1), "iv": "short"}},
    {"type": "loc", "env": {**fake_env(1), "v": 2}},
    {"type": "hello"},
    {"type": "end", "reason": "bored"},
])
def test_e2ee_rejects_wrong_kind(client, msg):
    j = new_journey(client)
    with _ws(client, j["journey_id"]) as w:
        auth(w, "walker", j["walker_token"])
        send(w, msg)
        assert close_code(w) == 4400


def test_oversize_message(client):
    j = new_journey(client)
    with _ws(client, j["journey_id"]) as w:
        auth(w, "walker", j["walker_token"])
        send(w, {"type": "loc", "env": fake_env(1, ct_len=3500)})
        assert close_code(w) == 4413


def test_rate_limit(client):
    j = new_journey(client)
    with _ws(client, j["journey_id"]) as w:
        auth(w, "walker", j["walker_token"])
        for i in range(1, 7):
            send(w, {"type": "loc", "env": fake_env(i)})
        assert close_code(w) == 4429


def test_new_walker_replaces_old(client):
    j = new_journey(client)
    with _ws(client, j["journey_id"]) as w1:
        auth(w1, "walker", j["walker_token"])
        with _ws(client, j["journey_id"]) as w2:
            auth(w2, "walker", j["walker_token"])
            assert close_code(w1) == 4409
            hub = client.app.state.waykin.relay
            assert j["journey_id"] in hub.walkers


def test_max_viewers(client):
    j = new_journey(client)
    socks = [_ws(client, j["journey_id"]) for _ in range(6)]
    opened = [s.__enter__() for s in socks]
    try:
        for v in opened[:5]:
            assert auth(v, "viewer", j["viewer_token"])["type"] == "ready"
        opened[5].send_text(json.dumps({"type": "auth", "role": "viewer", "token": j["viewer_token"]}))
        assert close_code(opened[5]) == 4429
    finally:
        for s in socks:
            s.__exit__(None, None, None)


def test_auth_must_be_first(client):
    j = new_journey(client)
    with _ws(client, j["journey_id"]) as w:
        send(w, {"type": "loc", "env": fake_env(1)})
        assert close_code(w) == 4400


def test_unknown_journey(client):
    with _ws(client, "nope") as w:
        send(w, {"type": "auth", "role": "viewer", "token": "x"})
        assert close_code(w) == 4404


def test_delete_journey(client):
    j = new_journey(client)
    jid = j["journey_id"]
    with _ws(client, jid) as v:
        auth(v, "viewer", j["viewer_token"])
        assert client.delete(f"/api/journeys/{jid}",
                             headers={"Authorization": f"Bearer {j['viewer_token']}"}).status_code == 401
        r = client.delete(f"/api/journeys/{jid}", headers={"Authorization": f"Bearer {j['walker_token']}"})
        assert r.status_code == 204
        assert v.receive_json() == {"type": "ended", "reason": "stopped"}
        assert close_code(v) == 4410
    r = client.delete(f"/api/journeys/{jid}", headers={"Authorization": f"Bearer {j['walker_token']}"})
    assert r.status_code == 404 and r.json()["error"]["code"] == "not_found"


def test_delete_requires_bearer(client):
    j = new_journey(client)
    r = client.delete(f"/api/journeys/{j['journey_id']}")
    assert r.status_code == 401 and r.json()["error"]["code"] == "invalid_token"
