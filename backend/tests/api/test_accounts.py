"""Accounts, families, invites, the family stream and the relay additions (H20 completion work)."""
import json

import pytest

PW = "correct horse battery"
WRAPPED = "w" * 40


def sign_up(c, login, name=None) -> dict:
    """Sign up and return headers carrying that person's session. Clears the shared cookie jar."""
    r = c.post("/api/me/account", json={"display_name": name or login.title(), "login": login, "password": PW})
    assert r.status_code == 201, r.text
    token = r.cookies["wk_session"]
    c.cookies.clear()
    return {"Cookie": f"wk_session={token}"}


def family_with(c, owner_h, *members_h) -> str:
    fid = c.post("/api/me/families", json={"name": "Home", "wrapped_key": WRAPPED}, headers=owner_h).json()["family_id"]
    for h in members_h:
        tok = c.post(f"/api/me/families/{fid}/invites", headers=owner_h).json()["invite_token"]
        r = c.post(f"/api/me/families/{fid}/join", json={"invite_token": tok, "wrapped_key": WRAPPED, "key_version": 1},
                   headers=h)
        assert r.status_code == 200, r.text
    return fid


# ------------------------------------------------------------ accounts
def test_sign_up_sets_a_scoped_http_only_cookie(mock_client):
    r = mock_client.post("/api/me/account", json={"display_name": "Sam", "login": "sam", "password": PW})
    assert r.status_code == 201 and r.json()["display_name"] == "Sam"
    cookie = r.headers["set-cookie"].lower()
    assert "path=/api/me" in cookie and "httponly" in cookie and "samesite=strict" in cookie
    assert mock_client.get("/api/me/account").json()["login"] == "sam"


def test_session_cookie_never_reaches_the_route_endpoints(mock_client):
    mock_client.post("/api/me/account", json={"display_name": "Sam", "login": "sam", "password": PW})
    body = {"origin": {"lat": 53.52, "lon": -113.52}, "destination": {"lat": 53.521, "lon": -113.5}}
    for path in ("/api/routes", "/api/routes/reroute"):
        payload = body if path == "/api/routes" else {"position": body["origin"], "destination": body["destination"]}
        r = mock_client.post(path, json=payload)
        assert "cookie" not in {k.lower() for k in r.request.headers}


def test_password_is_hashed_and_wrong_login_looks_like_unknown_login(mock_client):
    sign_up(mock_client, "sam")
    db = mock_client.app.state.waykin.accounts
    row = db._q("SELECT pw_hash, pw_salt FROM accounts WHERE login = 'sam'")[0]
    assert PW.encode() not in bytes(row["pw_hash"]) and len(row["pw_hash"]) == 32
    wrong = mock_client.post("/api/me/session", json={"login": "sam", "password": "nope nope nope"})
    unknown = mock_client.post("/api/me/session", json={"login": "nobody", "password": "nope nope nope"})
    assert wrong.status_code == unknown.status_code == 401
    assert wrong.json() == unknown.json()


def test_duplicate_login_is_refused(mock_client):
    sign_up(mock_client, "sam")
    r = mock_client.post("/api/me/account", json={"display_name": "X", "login": "SAM", "password": PW})
    assert r.status_code == 409


def test_login_is_rate_limited(mock_client):
    sign_up(mock_client, "sam")
    codes = [mock_client.post("/api/me/session", json={"login": "sam", "password": "wrong wrong"}).status_code
             for _ in range(7)]
    assert codes[:5] == [401] * 5 and codes[-1] == 429


def test_log_out_and_delete_account(mock_client):
    h = sign_up(mock_client, "sam")
    assert mock_client.get("/api/me/account", headers=h).status_code == 200
    assert mock_client.delete("/api/me/session", headers=h).status_code == 204
    assert mock_client.get("/api/me/account", headers=h).status_code == 401
    h = {"Cookie": f"wk_session={mock_client.post('/api/me/session', json={'login': 'sam', 'password': PW}).cookies['wk_session']}"}
    mock_client.cookies.clear()
    assert mock_client.delete("/api/me/account", headers=h).status_code == 204
    assert mock_client.app.state.waykin.accounts._q("SELECT COUNT(*) AS n FROM accounts")[0]["n"] == 0


def test_me_endpoints_need_a_session(mock_client):
    assert mock_client.get("/api/me/account").status_code == 401
    assert mock_client.get("/api/me/families").status_code == 401


# ------------------------------------------------------------ families and invites
def test_invite_flow_is_single_use_and_stores_no_raw_key(mock_client):
    owner, alex, kim = sign_up(mock_client, "owner"), sign_up(mock_client, "alex"), sign_up(mock_client, "kim")
    fid = family_with(mock_client, owner, alex)
    detail = mock_client.get(f"/api/me/families/{fid}", headers=alex).json()
    assert {m["display_name"] for m in detail["members"]} == {"Owner", "Alex"}
    assert detail["my_wrapped_key"] == WRAPPED and detail["key_version"] == 1

    tok = mock_client.post(f"/api/me/families/{fid}/invites", headers=owner).json()["invite_token"]
    prev = mock_client.post(f"/api/me/families/{fid}/invite-preview", json={"invite_token": tok}, headers=kim).json()
    assert prev == {"family_name": "Home", "invited_by": "Owner"}
    join = {"invite_token": tok, "wrapped_key": WRAPPED, "key_version": 1}
    assert mock_client.post(f"/api/me/families/{fid}/join", json=join, headers=kim).status_code == 200
    stranger = sign_up(mock_client, "stranger")
    assert mock_client.post(f"/api/me/families/{fid}/join", json=join, headers=stranger).status_code == 404
    db = mock_client.app.state.waykin.accounts
    assert db._q("SELECT COUNT(*) AS n FROM invites WHERE token_hash = ?", (tok.encode(),))[0]["n"] == 0  # hashed


def test_non_members_get_404_not_403(mock_client):
    owner, stranger = sign_up(mock_client, "owner"), sign_up(mock_client, "stranger")
    fid = family_with(mock_client, owner)
    assert mock_client.get(f"/api/me/families/{fid}", headers=stranger).status_code == 404
    assert mock_client.get("/api/me/families/does-not-exist", headers=stranger).status_code == 404
    assert mock_client.post(f"/api/me/families/{fid}/invites", headers=stranger).status_code == 404


def test_only_the_owner_removes_others_and_rotation_drops_old_invites(mock_client):
    owner, alex, kim = sign_up(mock_client, "owner"), sign_up(mock_client, "alex"), sign_up(mock_client, "kim")
    fid = family_with(mock_client, owner, alex, kim)
    ids = {m["display_name"]: m["account_id"] for m in mock_client.get(f"/api/me/families/{fid}", headers=owner).json()["members"]}
    assert mock_client.delete(f"/api/me/families/{fid}/members/{ids['Kim']}", headers=alex).status_code == 403
    old_invite = mock_client.post(f"/api/me/families/{fid}/invites", headers=owner).json()["invite_token"]
    assert mock_client.delete(f"/api/me/families/{fid}/members/{ids['Kim']}", headers=owner).status_code == 204
    assert mock_client.get(f"/api/me/families/{fid}", headers=kim).status_code == 404
    bad = mock_client.put(f"/api/me/families/{fid}/keys", json={"key_version": 2, "wrapped": {ids["Owner"]: WRAPPED}},
                          headers=owner)
    assert bad.status_code == 422   # must cover every remaining member
    new = {ids["Owner"]: "n" * 40, ids["Alex"]: "m" * 40}
    assert mock_client.put(f"/api/me/families/{fid}/keys", json={"key_version": 2, "wrapped": new},
                           headers=owner).status_code == 204
    assert mock_client.get(f"/api/me/families/{fid}", headers=alex).json()["my_wrapped_key"] == "m" * 40
    late = sign_up(mock_client, "late")
    r = mock_client.post(f"/api/me/families/{fid}/join",
                         json={"invite_token": old_invite, "wrapped_key": WRAPPED, "key_version": 1}, headers=late)
    assert r.status_code == 404


def test_member_can_leave_and_ownership_passes_on(mock_client):
    owner, alex = sign_up(mock_client, "owner"), sign_up(mock_client, "alex")
    fid = family_with(mock_client, owner, alex)
    me = mock_client.get("/api/me/account", headers=owner).json()["account_id"]
    assert mock_client.delete(f"/api/me/families/{fid}/members/{me}", headers=owner).status_code == 204
    assert mock_client.get(f"/api/me/families/{fid}", headers=alex).json()["owner_id"] != me


# ------------------------------------------------------------ family journeys and stream
def test_family_journey_is_announced_and_ended_on_the_stream(mock_client):
    owner, alex = sign_up(mock_client, "owner"), sign_up(mock_client, "alex")
    fid = family_with(mock_client, owner, alex)
    with mock_client.websocket_connect("/api/me/stream", headers=alex) as stream:
        assert stream.receive_json()["type"] == "ready"
        r = mock_client.post(f"/api/me/families/{fid}/journeys",
                             json={"wrapped_journey_key": WRAPPED, "key_version": 1}, headers=owner)
        assert r.status_code == 201
        jid, walker_token = r.json()["journey_id"], r.json()["walker_token"]
        ev = stream.receive_json()
        assert ev["type"] == "journey.started" and ev["journey"]["journey_id"] == jid
        assert ev["journey"]["walker_display_name"] == "Owner" and "lat" not in json.dumps(ev)
        listed = mock_client.get(f"/api/me/families/{fid}", headers=alex).json()["journeys"]
        assert [j["journey_id"] for j in listed] == [jid]
        with mock_client.websocket_connect(f"/api/relay/{jid}") as w:
            w.send_json({"type": "auth", "role": "walker", "token": walker_token})
            w.receive_json()
            w.send_json({"type": "end", "reason": "arrived"})
        ev = stream.receive_json()
        assert ev == {"type": "journey.ended", "journey_id": jid, "family_id": fid, "reason": "arrived"}
    assert mock_client.get(f"/api/me/families/{fid}", headers=alex).json()["journeys"] == []


def test_stream_refuses_without_a_session(mock_client):
    from starlette.websockets import WebSocketDisconnect
    with pytest.raises(WebSocketDisconnect):
        with mock_client.websocket_connect("/api/me/stream") as s:
            s.receive_json()


def test_stale_family_key_cannot_start_a_journey(mock_client):
    owner = sign_up(mock_client, "owner")
    fid = family_with(mock_client, owner)
    r = mock_client.post(f"/api/me/families/{fid}/journeys", json={"wrapped_journey_key": WRAPPED, "key_version": 7},
                         headers=owner)
    assert r.status_code == 409


# ------------------------------------------------------------ relay additions
def test_walker_hears_viewer_counts_and_labels(mock_client):
    j = mock_client.post("/api/journeys", json={}).json()
    with mock_client.websocket_connect(f"/api/relay/{j['journey_id']}") as w:
        w.send_json({"type": "auth", "role": "walker", "token": j["walker_token"]})
        assert w.receive_json()["type"] == "ready"
        assert w.receive_json() == {"type": "viewers", "count": 0}
        with mock_client.websocket_connect(f"/api/relay/{j['journey_id']}") as v:
            v.send_json({"type": "auth", "role": "viewer", "token": j["viewer_token"], "label": " Alex\n"})
            v.receive_json()
            assert w.receive_json() == {"type": "viewer_joined", "count": 1, "label": "Alex"}
        assert w.receive_json() == {"type": "viewer_left", "count": 0}


def test_viewers_hear_when_the_walker_goes_silent(mock_client):
    import asyncio
    j = mock_client.post("/api/journeys", json={}).json()
    relay = mock_client.app.state.waykin.relay
    with mock_client.websocket_connect(f"/api/relay/{j['journey_id']}") as w:
        w.send_json({"type": "auth", "role": "walker", "token": j["walker_token"]})
        w.receive_json()
        with mock_client.websocket_connect(f"/api/relay/{j['journey_id']}") as v:
            v.send_json({"type": "auth", "role": "viewer", "token": j["viewer_token"]})
            v.receive_json()
            mock_client.portal.call(relay.check_silence, 0)
            msg = v.receive_json()
            assert msg["type"] == "walker_silent" and set(msg) == {"type", "silent_s"}
            mock_client.portal.call(relay.check_silence, 0)      # sent once, not repeatedly
            w.send_json({"type": "loc", "plain": {"lat": 53.52, "lon": -113.52, "accuracy_m": 5, "ts": 1,
                                                  "status": "walking", "eta_min": 3, "alert": {"kind": "stopped", "ts": 1}}})
            assert v.receive_json()["plain"]["alert"]["kind"] == "stopped"
    assert asyncio is not None
